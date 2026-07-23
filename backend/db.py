import os
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id          SERIAL PRIMARY KEY,
                ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source      TEXT NOT NULL,
                asset       TEXT NOT NULL,
                amount      DOUBLE PRECISION NOT NULL,
                value_usd   DOUBLE PRECISION,
                value_eur   DOUBLE PRECISION,
                currency    TEXT
            );
            CREATE INDEX IF NOT EXISTS snapshots_ts_idx ON snapshots(ts DESC);
            CREATE INDEX IF NOT EXISTS snapshots_source_idx ON snapshots(source);
            ALTER TABLE snapshots ADD COLUMN IF NOT EXISTS value_eur DOUBLE PRECISION;
        """)
        conn.commit()


def insert_snapshot(conn, source: str, rows: list[dict]):
    ts = datetime.now(timezone.utc)
    data = [(ts, source, r["asset"], r["amount"], r.get("value_usd"), r.get("value_eur"), r.get("currency")) for r in rows]
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO snapshots (ts, source, asset, amount, value_usd, value_eur, currency)
            VALUES %s
        """, data)
    conn.commit()
