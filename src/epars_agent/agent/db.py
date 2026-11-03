"""
ePARS PostgreSQL connection manager.

All database callers should use:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(...)

Connections are returned to a small thread-safe pool after each use.
"""

import os
from contextlib import contextmanager
from threading import Lock

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

_pool = None
_pool_lock = Lock()


def _create_pool():
    """Create the connection pool once, on first database use."""
    global _pool

    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is not None:
            return _pool

        min_connections = int(os.getenv("DB_POOL_MIN", "1"))
        max_connections = int(os.getenv("DB_POOL_MAX", "5"))

        if min_connections < 1 or max_connections < min_connections:
            raise ValueError("Invalid DB_POOL_MIN / DB_POOL_MAX configuration.")

        if DATABASE_URL:
            pool_kwargs = {"dsn": DATABASE_URL}
        else:
            required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
            missing = [key for key in required if not os.getenv(key)]
            if missing:
                raise RuntimeError(
                    "Missing database environment variables: "
                    + ", ".join(missing)
                    + ". Set DATABASE_URL or all required DB_* variables."
                )

            pool_kwargs = {
                "host": os.environ["DB_HOST"],
                "port": int(os.getenv("DB_PORT", "5432")),
                "dbname": os.environ["DB_NAME"],
                "user": os.environ["DB_USER"],
                "password": os.environ["DB_PASSWORD"],
            }

        _pool = ThreadedConnectionPool(
            min_connections,
            max_connections,
            cursor_factory=psycopg2.extras.RealDictCursor,
            **pool_kwargs,
        )

    return _pool


@contextmanager
def get_connection():
    """
    Borrow a connection from the pool.

    The transaction is committed on success and rolled back on failure.
    The connection is always returned to the pool.
    """
    pool = _create_pool()
    conn = pool.getconn()

    try:
        if conn.closed:
            pool.putconn(conn, close=True)
            conn = pool.getconn()

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        if conn is not None:
            pool.putconn(conn, close=bool(conn.closed))


def close_connection_pool():
    """Close all pooled connections; useful during application shutdown."""
    global _pool

    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


def test_connection():
    """Run this file directly to verify database connectivity."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version() AS version;")
                row = cur.fetchone()
                print(f"[OK] Connected to PostgreSQL: {row['version']}")
    except Exception as exc:
        print(f"[ERROR] Could not connect to PostgreSQL: {exc}")


if __name__ == "__main__":
    test_connection()
