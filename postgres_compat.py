"""Small compatibility layer that lets the existing app use PostgreSQL.

The application was originally written against sqlite3.  This wrapper keeps its
``db.execute(...).fetchone()`` calling style while translating SQLite's ``?``
placeholders to PostgreSQL's ``%s`` placeholders.
"""

import re

from psycopg import connect
from psycopg.rows import dict_row


def normalize_database_url(database_url):
    """Require encrypted connections when using a hosted PostgreSQL database."""
    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        return f"{database_url}{separator}sslmode=require"
    return database_url


class CompatibleRow(dict):
    """PostgreSQL dictionary row that also supports SQLite-style numeric access."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class QueryResult:
    def __init__(self, rows=()):
        self._rows = [CompatibleRow(row) for row in rows]

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class PostgreSQLConnection:
    """Expose the subset of sqlite3.Connection used by this application."""

    def __init__(self, database_url):
        self._connection = connect(normalize_database_url(database_url), row_factory=dict_row)

    def execute(self, query, params=()):
        # Every current query uses qmark placeholders. PostgreSQL uses %s.
        postgresql_query = re.sub(r"\?", "%s", query)
        with self._connection.cursor() as cursor:
            cursor.execute(postgresql_query, params)
            rows = cursor.fetchall() if cursor.description else ()
        return QueryResult(rows)

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()
