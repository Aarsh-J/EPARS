"""
ePARS — Database Connection Module
====================================
Single place that manages the PostgreSQL connection.
Every tool function imports `get_connection` from here.

Setup:
    Copy .env.example to .env and fill in your credentials.
    Then just import and use — no other setup needed.
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()  # reads .env file from project root

DATABASE_URL = os.getenv("DATABASE_URL")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME",     "epars_db"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}


def get_connection():
    """
    Returns a new psycopg2 connection.
    Uses DATABASE_URL if set (e.g. Supabase connection string), otherwise
    falls back to the individual DB_* vars.

    Always use as a context manager so it auto-closes:

        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT ...")
                rows = cur.fetchall()
    """
    if DATABASE_URL:
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    return psycopg2.connect(
        **DB_CONFIG,
        cursor_factory=psycopg2.extras.RealDictCursor  # rows come back as dicts
    )


def test_connection():
    """Quick health check — run this file directly to verify DB is reachable."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()
                print(f"[OK] Connected to PostgreSQL: {version['version']}")
    except Exception as e:
        print(f"[ERROR] Could not connect to PostgreSQL: {e}")
        print("  Check your .env file and make sure PostgreSQL is running.")


if __name__ == "__main__":
    test_connection()
