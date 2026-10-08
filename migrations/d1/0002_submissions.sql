-- D1 migration 0002: submissions / payment tracking table
-- Apply via: wrangler d1 execute <DB_NAME> --file=migrations/d1/0002_submissions.sql
-- Or via: python scripts/apply_d1_schema.py

CREATE TABLE IF NOT EXISTS submissions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT    NOT NULL COLLATE NOCASE,
    consumer_number  TEXT    NOT NULL,
    payment_status   TEXT    NOT NULL DEFAULT 'UNPAID' CHECK (payment_status IN ('PAID', 'UNPAID')),
    submitted_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (username, consumer_number)
);

CREATE INDEX IF NOT EXISTS idx_submissions_username        ON submissions (username COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_submissions_payment_status ON submissions (payment_status);
