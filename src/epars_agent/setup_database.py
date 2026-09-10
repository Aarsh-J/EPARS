"""
ePARS — PostgreSQL Setup Script
=================================
Run this ONCE to:
  1. Create all 10 tables with correct column types
  2. Load all 10 CSV files into those tables

Usage:
    python setup_database.py

Requirements:
    pip install psycopg2-binary pandas python-dotenv

Make sure your .env file has the correct DB credentials before running.
CSV files are expected in <worktree_root>/dataset/ (resolved relative to this
file's location, not CWD — see CSV_DIR below).
"""

import os
import re
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from io import StringIO
from pathlib import Path

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
# Resolved relative to this file (src/epars_agent/) rather than CWD, so it works
# regardless of where `python setup_database.py` is run from.
CSV_DIR = str(Path(__file__).resolve().parent.parent.parent / "dataset")

DATABASE_URL = os.getenv("DATABASE_URL")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME",     "epars_db"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# ── Table DDL ──────────────────────────────────────────────────────────────────
# Each CREATE TABLE matches the exact columns in your CSVs.
# Tables are created in dependency order (employees first, then everything
# that references it).

TABLES_DDL = [

# ── 1. employees ──────────────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS employees (
    employee_id                  VARCHAR(20)  PRIMARY KEY,
    first_name                   VARCHAR(100),
    last_name                    VARCHAR(100),
    email                        VARCHAR(200),
    department                   VARCHAR(100),
    role                         VARCHAR(100),
    seniority_level              VARCHAR(50),
    employment_type              VARCHAR(50),
    hire_date                    DATE,
    years_of_experience          NUMERIC(5,2),
    current_salary               NUMERIC(12,2),
    primary_skills               TEXT,
    secondary_skills             TEXT,
    certifications               TEXT,
    technical_proficiency_score  NUMERIC(6,2),
    domain_expertise_score       NUMERIC(6,2),
    weekly_capacity_hours        INTEGER,
    is_available                 BOOLEAN,
    current_project_count        INTEGER,
    preferred_work_hours         VARCHAR(50),
    remote_work_status           VARCHAR(50),
    historical_performance_score NUMERIC(6,2),
    productivity_trend           VARCHAR(50),
    average_task_completion_rate NUMERIC(6,2),
    collaboration_score          INTEGER,
    leadership_potential         NUMERIC(6,2),
    stress_level                 VARCHAR(20),
    burnout_risk_score           NUMERIC(6,4),
    recent_overtime_hours        NUMERIC(6,2),
    days_since_last_leave        INTEGER,
    preferred_team_size          VARCHAR(50),
    past_team_members            TEXT,
    successful_project_count     INTEGER,
    failed_project_count         INTEGER,
    created_at                   TIMESTAMP,
    last_updated                 TIMESTAMP
)
""",

# ── 2. projects ───────────────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS projects (
    project_id              VARCHAR(20)  PRIMARY KEY,
    project_name            VARCHAR(200),
    project_description     TEXT,
    project_type            VARCHAR(100),
    department              VARCHAR(100),
    priority                VARCHAR(20),
    budget                  NUMERIC(14,2),
    complexity_level        VARCHAR(50),
    start_date              DATE,
    planned_end_date        DATE,
    actual_end_date         DATE,
    current_status          VARCHAR(50),
    completion_percentage   NUMERIC(6,2),
    is_on_schedule          BOOLEAN,
    days_ahead_behind       INTEGER,
    project_manager_id      VARCHAR(20),
    team_member_ids         TEXT,
    team_size               INTEGER,
    required_skills         TEXT,
    allocated_resources     INTEGER,
    consumed_resources      INTEGER,
    success_probability     NUMERIC(6,2),
    delay_risk_score        NUMERIC(6,2),
    budget_overrun_risk     NUMERIC(6,2),
    quality_risk_score      NUMERIC(6,2),
    scope_creep_indicator   NUMERIC(6,2),
    stakeholder_satisfaction NUMERIC(5,2),
    roi_estimate            NUMERIC(8,2),
    total_milestones        INTEGER,
    completed_milestones    INTEGER,
    overdue_milestones      INTEGER,
    next_milestone_date     DATE,
    next_milestone_risk     NUMERIC(6,2),
    created_at              TIMESTAMP,
    last_updated            TIMESTAMP
)
""",

# ── 3. tasks ──────────────────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS tasks (
    task_id                  VARCHAR(20)  PRIMARY KEY,
    task_name                VARCHAR(200),
    task_description         TEXT,
    task_type                VARCHAR(100),
    project_id               VARCHAR(20),
    priority                 VARCHAR(20),
    complexity               VARCHAR(50),
    estimated_hours          NUMERIC(8,2),
    actual_hours             NUMERIC(8,2),
    story_points             INTEGER,
    required_skills          TEXT,
    required_role            VARCHAR(100),
    required_seniority       VARCHAR(50),
    assigned_to              VARCHAR(20),
    assigned_date            DATE,
    status                   VARCHAR(50),
    completion_percentage    NUMERIC(6,2),
    start_date               DATE,
    due_date                 DATE,
    actual_completion_date   DATE,
    is_overdue               BOOLEAN,
    days_overdue             INTEGER,
    buffer_days              INTEGER,
    dependent_task_ids       TEXT,
    blocking_task_ids        TEXT,
    parent_task_id           VARCHAR(20),
    quality_score            NUMERIC(4,2),
    rework_required          BOOLEAN,
    rework_count             INTEGER,
    review_rating            NUMERIC(4,2),
    stakeholder_satisfaction NUMERIC(4,2),
    risk_level               VARCHAR(20),
    business_impact          VARCHAR(50),
    delay_risk_score         NUMERIC(6,2),
    requires_collaboration   BOOLEAN,
    team_size_required       INTEGER,
    created_at               TIMESTAMP,
    last_updated             TIMESTAMP
)
""",

# ── 4. task_assignments ───────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS task_assignments (
    assignment_id                VARCHAR(20)  PRIMARY KEY,
    task_id                      VARCHAR(20),
    employee_id                  VARCHAR(20),
    project_id                   VARCHAR(20),
    assignment_date              DATE,
    assignment_method            VARCHAR(50),
    assigned_by                  VARCHAR(20),
    acceptance_status            VARCHAR(50),
    acceptance_date              DATE,
    skill_match_score            NUMERIC(6,2),
    availability_match_score     NUMERIC(6,2),
    workload_compatibility_score NUMERIC(6,2),
    experience_match_score       NUMERIC(6,2),
    overall_suitability_score    NUMERIC(6,2),
    team_compatibility_score     NUMERIC(6,2),
    assignment_success           BOOLEAN,
    completion_status            VARCHAR(50),
    reassignment_count           INTEGER,
    reassignment_reason          TEXT,
    quality_rating               NUMERIC(4,2),
    on_time_completion           BOOLEAN,
    efficiency_score             NUMERIC(6,2),
    assignment_satisfaction      INTEGER,
    created_at                   TIMESTAMP,
    last_updated                 TIMESTAMP
)
""",

# ── 5. schedules ──────────────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id              VARCHAR(20)  PRIMARY KEY,
    employee_id              VARCHAR(20),
    event_type               VARCHAR(50),
    related_id               VARCHAR(50),
    event_title              VARCHAR(200),
    date                     DATE,
    start_time               TIME,
    end_time                 TIME,
    duration_minutes         INTEGER,
    priority                 VARCHAR(20),
    is_flexible              BOOLEAN,
    buffer_minutes           INTEGER,
    conflict_with_ids        TEXT,
    optimization_score       NUMERIC(6,2),
    recommended_time         TIME,
    attendance_status        VARCHAR(50),
    actual_start_time        TIME,
    actual_end_time          TIME,
    actual_duration_minutes  NUMERIC(6,2),
    productivity_during      NUMERIC(6,2),
    involves_team            BOOLEAN,
    participant_ids          TEXT,
    participant_count        INTEGER,
    meeting_type             VARCHAR(50),
    location                 VARCHAR(100),
    is_remote                BOOLEAN,
    meeting_link             VARCHAR(200),
    created_at               TIMESTAMP,
    last_updated             TIMESTAMP
)
""",

# ── 6. workload_history ───────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS workload_history (
    record_id                VARCHAR(20)  PRIMARY KEY,
    employee_id              VARCHAR(20),
    date                     DATE,
    week_number              INTEGER,
    total_hours_worked       NUMERIC(6,2),
    overtime_hours           NUMERIC(6,2),
    billable_hours           NUMERIC(6,2),
    non_billable_hours       NUMERIC(6,2),
    meeting_hours            NUMERIC(6,2),
    focused_work_hours       NUMERIC(6,2),
    context_switching_count  INTEGER,
    active_tasks_count       INTEGER,
    active_projects_count    INTEGER,
    tasks_completed          INTEGER,
    tasks_started            INTEGER,
    blocked_tasks_count      INTEGER,
    high_priority_tasks      INTEGER,
    workload_intensity_score NUMERIC(6,2),
    deadline_pressure_score  NUMERIC(6,2),
    productivity_score       NUMERIC(6,2),
    efficiency_ratio         NUMERIC(6,2),
    task_completion_rate     NUMERIC(6,2),
    quality_of_work          NUMERIC(4,2),
    rework_time_hours        NUMERIC(6,2),
    meetings_attended        INTEGER,
    collaboration_hours      NUMERIC(6,2),
    stress_level             VARCHAR(20),
    weekend_work_indicator   BOOLEAN,
    break_time_minutes       NUMERIC(8,2),
    productivity_vs_avg      NUMERIC(8,2),
    workload_vs_capacity     NUMERIC(8,2),
    burnout_risk_today       NUMERIC(6,2),
    special_circumstances    VARCHAR(100),
    out_of_office            BOOLEAN,
    worked_from              VARCHAR(50),
    created_at               TIMESTAMP
)
""",

# ── 7. team_formations ────────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS team_formations (
    team_id                      VARCHAR(20)  PRIMARY KEY,
    team_name                    VARCHAR(200),
    project_id                   VARCHAR(20),
    formation_date               DATE,
    formation_method             VARCHAR(50),
    team_lead_id                 VARCHAR(20),
    member_ids                   TEXT,
    team_size                    INTEGER,
    role_distribution            TEXT,
    seniority_mix                TEXT,
    skill_diversity_score        NUMERIC(6,2),
    experience_balance_score     NUMERIC(6,2),
    collaborative_history_score  NUMERIC(6,2),
    workload_balance_score       NUMERIC(6,2),
    predicted_success_rate       NUMERIC(6,2),
    actual_performance_score     NUMERIC(6,2),
    collaboration_effectiveness  NUMERIC(6,2),
    project_completed            BOOLEAN,
    completion_time_days         NUMERIC(8,2),
    met_deadline                 BOOLEAN,
    quality_rating               NUMERIC(4,2),
    budget_adherence             NUMERIC(6,2),
    stakeholder_satisfaction     NUMERIC(4,2),
    resource_utilization         NUMERIC(6,2),
    skill_utilization_rate       NUMERIC(6,2),
    team_feedback_score          NUMERIC(4,2),
    team_status                  VARCHAR(50),
    dissolution_date             DATE,
    dissolution_reason           TEXT,
    created_at                   TIMESTAMP,
    last_updated                 TIMESTAMP
)
""",

# ── 8. feedback ───────────────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id          VARCHAR(20)  PRIMARY KEY,
    feedback_type        VARCHAR(50),
    provider_id          VARCHAR(20),
    recipient_id         VARCHAR(20),
    feedback_date        DATE,
    related_task_id      VARCHAR(20),
    related_project_id   VARCHAR(20),
    related_team_id      VARCHAR(20),
    feedback_category    VARCHAR(50),
    feedback_text        TEXT,
    positive_aspects     TEXT,
    improvement_areas    TEXT,
    specific_suggestions TEXT,
    action_items         TEXT,
    overall_rating       INTEGER,
    quality_rating       INTEGER,
    timeliness_rating    INTEGER,
    collaboration_rating INTEGER,
    communication_rating INTEGER,
    priority_level       VARCHAR(20),
    follow_up_date       DATE,
    acknowledged         BOOLEAN,
    acknowledged_date    DATE,
    recipient_response   TEXT,
    response_date        DATE,
    visibility           VARCHAR(50),
    created_at           TIMESTAMP,
    last_updated         TIMESTAMP
)
""",

# ── 9. performance_reviews ────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS performance_reviews (
    review_id                       VARCHAR(20)  PRIMARY KEY,
    employee_id                     VARCHAR(20),
    reviewer_id                     VARCHAR(20),
    review_period_start             DATE,
    review_period_end               DATE,
    review_date                     DATE,
    review_type                     VARCHAR(50),
    overall_performance_score       NUMERIC(6,2),
    normalized_performance_score    NUMERIC(6,2),
    technical_competence_score      INTEGER,
    domain_knowledge_score          INTEGER,
    problem_solving_score           INTEGER,
    quality_of_work_score           INTEGER,
    productivity_score              INTEGER,
    communication_score             INTEGER,
    collaboration_score             INTEGER,
    leadership_score                INTEGER,
    initiative_score                INTEGER,
    time_management_score           INTEGER,
    tasks_completed                 INTEGER,
    projects_completed              INTEGER,
    average_task_quality            NUMERIC(6,2),
    on_time_delivery_rate           NUMERIC(6,2),
    productivity_vs_peers           NUMERIC(8,2),
    total_hours_worked              NUMERIC(8,2),
    overtime_hours                  NUMERIC(6,2),
    strengths                       TEXT,
    achievements                    TEXT,
    weaknesses                      TEXT,
    improvement_areas               TEXT,
    reviewer_comments               TEXT,
    recommended_actions             TEXT,
    self_assessment_score           INTEGER,
    peer_feedback_summary           TEXT,
    promotion_recommended           BOOLEAN,
    salary_increase_percentage      NUMERIC(5,2),
    salary_adjustment_recommendation NUMERIC(10,2),
    training_recommendations        TEXT,
    performance_rating              VARCHAR(50),
    promotion_readiness             VARCHAR(50),
    created_at                      TIMESTAMP,
    last_updated                    TIMESTAMP
)
""",

# ── 10. burnout_indicators ────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS burnout_indicators (
    indicator_id                  VARCHAR(20)  PRIMARY KEY,
    employee_id                   VARCHAR(20),
    assessment_date               DATE,
    assessment_type               VARCHAR(50),
    overall_burnout_risk          NUMERIC(6,2),
    emotional_exhaustion_score    INTEGER,
    depersonalization_score       INTEGER,
    reduced_accomplishment_score  INTEGER,
    burnout_category              VARCHAR(50),
    role_ambiguity                INTEGER,
    job_control                   INTEGER,
    late_hours_frequency          INTEGER,
    weekend_work_frequency        INTEGER,
    missed_breaks_count           INTEGER,
    vacation_days_unused          INTEGER,
    sick_days_taken               INTEGER,
    absence_rate                  NUMERIC(6,2),
    job_satisfaction              INTEGER,
    social_support_score          INTEGER,
    manager_support_score         INTEGER,
    mental_health_support_needed  BOOLEAN,
    burnout_trend                 VARCHAR(50),
    predicted_burnout_30days      NUMERIC(6,2),
    predicted_burnout_90days      NUMERIC(6,2),
    intervention_urgency          VARCHAR(20),
    interventions_received        INTEGER,
    last_intervention_date        DATE,
    intervention_effectiveness    NUMERIC(6,2),
    created_at                    TIMESTAMP,
    last_updated                  TIMESTAMP
)
""",

]

# ── CSV loading config ─────────────────────────────────────────────────────────
# Maps each table name to its CSV filename and which columns need special handling.

CSV_LOAD_CONFIG = {
    "employees":           {"file": "employees.csv"},
    "projects":            {"file": "projects.csv"},
    "tasks":               {"file": "tasks.csv"},
    "task_assignments":    {"file": "task_assignments.csv"},
    "schedules":           {"file": "schedules.csv"},
    "workload_history":    {"file": "workload_history.csv"},
    "team_formations":     {"file": "team_formations.csv"},
    "feedback":            {"file": "feedback.csv"},
    "performance_reviews": {"file": "performance_reviews.csv"},
    "burnout_indicators":  {"file": "burnout_indicators.csv"},
}

# Columns that should become NULL when they contain NaN / empty strings
# (instead of trying to insert "nan" as a string into the DB)
NULLABLE_COLS = {
    "projects":         ["actual_end_date", "next_milestone_date", "next_milestone_risk"],
    "tasks":            ["assigned_to", "assigned_date", "actual_completion_date",
                         "dependent_task_ids", "blocking_task_ids", "parent_task_id"],
    "task_assignments": ["acceptance_date", "reassignment_reason"],
    "schedules":        ["related_id", "conflict_with_ids", "recommended_time"],
    "workload_history": ["special_circumstances"],
    "team_formations":  ["actual_performance_score", "completion_time_days",
                         "met_deadline", "budget_adherence", "stakeholder_satisfaction",
                         "dissolution_date", "dissolution_reason"],
    "feedback":         ["related_task_id", "related_project_id", "related_team_id",
                         "follow_up_date", "acknowledged_date", "recipient_response",
                         "response_date"],
    "burnout_indicators": ["intervention_urgency", "last_intervention_date",
                           "intervention_effectiveness"],
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def clean_df(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """
    Clean a dataframe before loading:
    - Replace NaN/None/"nan" strings with None (→ NULL in DB)
    - Normalise boolean columns
    """
    # Replace pandas NaN with None globally
    df = df.where(pd.notnull(df), None)

    # Replace string "nan" that sometimes survives the above
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].apply(
            lambda x: None if isinstance(x, str) and x.strip().lower() in ("nan", "none", "") else x
        )

    # Explicit nullability for known nullable columns
    for col in NULLABLE_COLS.get(table_name, []):
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: None if (x is None or (isinstance(x, float) and pd.isna(x))
                                   or (isinstance(x, str) and x.strip().lower() in ("nan", "none", ""))) else x
            )

    return df


def load_csv_to_table(conn, table_name: str, csv_path: str):
    """
    Loads a CSV into a PostgreSQL table using COPY for speed.
    Falls back to row-by-row insert if COPY fails.
    """
    print(f"  Loading {csv_path} → {table_name}...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = clean_df(df, table_name)
    row_count = len(df)

    # Use StringIO + COPY for fast bulk load
    buffer = StringIO()
    df.to_csv(buffer, index=False, header=False, na_rep="\\N")
    buffer.seek(0)

    try:
        with conn.cursor() as cur:
            cur.copy_expert(
                f"COPY {table_name} FROM STDIN WITH CSV NULL '\\N'",
                buffer
            )
        conn.commit()
        print(f"    ✓ {row_count:,} rows loaded into {table_name}")
    except Exception as e:
        conn.rollback()
        print(f"    ✗ COPY failed ({e}), trying row-by-row insert...")
        _insert_rows(conn, table_name, df)


def _insert_rows(conn, table_name: str, df: pd.DataFrame):
    """Fallback: insert row by row (slower but more tolerant of edge cases)."""
    cols = ", ".join(df.columns)
    placeholders = ", ".join(["%s"] * len(df.columns))
    sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    rows = [tuple(None if (v is None or (isinstance(v, float) and pd.isna(v))) else v
                  for v in row)
            for row in df.itertuples(index=False)]

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    conn.commit()
    print(f"    ✓ {len(rows):,} rows inserted into {table_name} (row-by-row)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("ePARS — PostgreSQL Setup")
    print("="*60)

    # Connect
    if DATABASE_URL:
        target = re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", DATABASE_URL)  # redact password
    else:
        target = f"{DB_CONFIG['host']}:{DB_CONFIG['port']}"
    print(f"\n[1/3] Connecting to PostgreSQL at {target}...")
    try:
        conn = psycopg2.connect(DATABASE_URL) if DATABASE_URL else psycopg2.connect(**DB_CONFIG)
        print("      ✓ Connected successfully")
    except Exception as e:
        print(f"      ✗ Connection failed: {e}")
        print("\n  Checklist:")
        print("  - Is PostgreSQL running?")
        print("  - Did you create the database? (CREATE DATABASE epars_db;)")
        print("  - Are .env credentials correct?")
        return

    # Create tables
    print(f"\n[2/3] Creating {len(TABLES_DDL)} tables...")
    with conn.cursor() as cur:
        for ddl in TABLES_DDL:
            table_name = [line for line in ddl.strip().split('\n')
                          if 'CREATE TABLE' in line][0].split('IF NOT EXISTS')[-1].strip().split('(')[0].strip()
            try:
                cur.execute(ddl)
                conn.commit()
                print(f"      ✓ {table_name}")
            except Exception as e:
                conn.rollback()
                print(f"      ✗ {table_name}: {e}")

    # Load CSVs
    print(f"\n[3/3] Loading CSV files from '{CSV_DIR}'...")
    for table_name, config in CSV_LOAD_CONFIG.items():
        csv_path = os.path.join(CSV_DIR, config["file"])
        if not os.path.exists(csv_path):
            print(f"  ✗ File not found: {csv_path} — skipping")
            continue
        load_csv_to_table(conn, table_name, csv_path)

    conn.close()

    print("\n" + "="*60)
    print("✓ Setup complete! All tables created and CSVs loaded.")
    print("="*60)
    print("\nNext step: run  python agent/db.py  to verify the connection.")
    print("Then run:        python agent/tools.py EMP001 TSK0001")


if __name__ == "__main__":
    main()
