"""Copy the project's current SQLite data into an empty Supabase PostgreSQL database."""

import argparse
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from psycopg import connect

from postgres_compat import normalize_database_url


ROOT = Path(__file__).resolve().parent
SQLITE_DATABASE = ROOT / "compliance_system.db"
SCHEMA_FILE = ROOT / "supabase_schema.sql"
TABLES = (
    "users", "consents", "dsr_requests", "incidents", "audit_logs",
    "processing_registry", "privacy_notices", "personal_data_inventory",
    "compliance_checklist",
)
BOOLEAN_COLUMNS = {"is_published", "npc_notified"}


def create_schema(connection):
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_FILE.read_text(encoding="utf-8"))


def target_contains_data(connection):
    with connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f"SELECT EXISTS (SELECT 1 FROM {table})")
            if cursor.fetchone()[0]:
                return True
    return False


def copy_table(source, target, table):
    rows = source.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        return 0
    # PRAGMA table_info returns: cid, name, type, notnull, default, primary-key.
    columns = [column[1] for column in source.execute(f"PRAGMA table_info({table})")]
    placeholders = ", ".join(["%s"] * len(columns))
    column_list = ", ".join(columns)
    values = []
    for row in rows:
        values.append(tuple(bool(row[column]) if column in BOOLEAN_COLUMNS and row[column] is not None else row[column] for column in columns))
    with target.cursor() as cursor:
        cursor.executemany(f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})", values)
        cursor.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table}"
        )
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true", help="Delete existing Supabase data before migration.")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required. Add it to .env or your environment before running this script.")
    if not SQLITE_DATABASE.exists():
        raise SystemExit(f"SQLite database not found: {SQLITE_DATABASE}")

    with sqlite3.connect(SQLITE_DATABASE) as source, connect(normalize_database_url(database_url)) as target:
        source.row_factory = sqlite3.Row
        create_schema(target)
        if target_contains_data(target):
            if not args.replace:
                raise SystemExit("Supabase already contains data. It was not changed. Re-run with --replace only if you intend to overwrite it.")
            with target.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE compliance_checklist, personal_data_inventory, privacy_notices, processing_registry, audit_logs, incidents, dsr_requests, consents, users RESTART IDENTITY CASCADE")
        for table in TABLES:
            print(f"{table}: copied {copy_table(source, target, table)} rows")


if __name__ == "__main__":
    main()
