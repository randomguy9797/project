#!/usr/bin/env python3
"""
Apply the D1 schema migration via the Cloudflare REST API.
No wrangler or Node.js required.

Usage:
    python scripts/apply_d1_schema.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.d1 import _query

# Each statement must be sent individually — D1 REST API executes one SQL
# statement per request.
STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        username         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        password_hash    TEXT    NOT NULL,
        is_admin         INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
        is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
        consumer_number  TEXT,
        created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users (username COLLATE NOCASE)",
]


def main() -> int:
    print("=== Applying D1 schema ===\n")
    for i, sql in enumerate(STATEMENTS, 1):
        label = sql.strip().split("\n")[0].strip()[:60]
        print(f"[{i}/{len(STATEMENTS)}] {label} ...")
        try:
            _query(sql.strip())
            print(f"  OK\n")
        except Exception as exc:
            print(f"  FAILED: {exc}\n")
            return 1
    print("Schema applied successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
