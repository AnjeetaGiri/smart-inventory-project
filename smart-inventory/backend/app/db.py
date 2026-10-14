from contextlib import contextmanager
import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    url = os.getenv("DATABASE_URL")
    if not url:
        # ECS injects these values from Secrets Manager; local development may use DATABASE_URL.
        host = os.getenv("DB_HOST")
        if not host:
            raise RuntimeError("Set DATABASE_URL or DB_HOST in the environment")
        return psycopg2.connect(
            host=host,
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "smartinventory"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            sslmode=os.getenv("DB_SSLMODE", "require"),
            cursor_factory=RealDictCursor,
        )
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


@contextmanager
def database():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
