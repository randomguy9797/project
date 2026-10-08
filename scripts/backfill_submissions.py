#!/usr/bin/env python3
"""Backfill D1 payment records from submission metadata already stored in R2.

The script can be run repeatedly.  ``db_upsert_submission`` preserves existing
payment statuses and only creates missing rows, so it is safe to resume after
an interruption.

Usage:
    python scripts/backfill_submissions.py
    python scripts/backfill_submissions.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.d1 import db_upsert_submission
from app.storage import get_consumer_details, list_consumer_users


def _iter_submissions():
    """Yield distinct (username, consumer_number) pairs found in R2 metadata."""
    for user in list_consumer_users():
        username = user["username"]
        for consumer in get_consumer_details(username):
            consumer_number = str(consumer.get("consumer_number", "")).strip()
            if consumer_number:
                yield username, consumer_number


def backfill(*, dry_run: bool = False) -> tuple[int, int]:
    """Backfill records and return ``(inserted, skipped)``."""
    inserted = skipped = 0
    for username, consumer_number in _iter_submissions():
        if dry_run:
            print(f"would backfill {username!r} / {consumer_number!r}")
            inserted += 1
            continue
        outcome = db_upsert_submission(username, consumer_number)
        if outcome == "inserted":
            inserted += 1
            print(f"inserted {username!r} / {consumer_number!r}")
        else:
            skipped += 1
            print(f"already present {username!r} / {consumer_number!r}")
    return inserted, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="List R2 submissions without writing to D1."
    )
    args = parser.parse_args(argv)
    try:
        inserted, skipped = backfill(dry_run=args.dry_run)
    except Exception as exc:
        print(f"Backfill failed: {exc}", file=sys.stderr)
        return 1

    verb = "would insert" if args.dry_run else "inserted"
    print(f"Backfill complete: {verb} {inserted}; skipped {skipped} existing record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
