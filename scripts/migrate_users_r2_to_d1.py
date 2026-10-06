#!/usr/bin/env python3
"""
Migrate users from R2 login/users.json → Cloudflare D1.

Usage:
    python scripts/migrate_users_r2_to_d1.py

Behaviour:
- Reads login/users.json from R2 (never modifies or deletes it).
- Validates every record before touching D1.
- Uses upsert: existing users are updated; new users are inserted.
- Prints a summary with counts; never prints passwords or hashes.
- Verifies each imported record against the source after import.
- Exits non-zero on any failure so CI/CD pipelines can detect problems.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage import get_json_object, USERS_OBJECT_KEY
from app.d1 import db_upsert_user, db_get_user

REQUIRED_FIELDS = {"username", "password_hash"}


def _validate(record: dict, index: int) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if not record.get(field):
            errors.append(f"record[{index}] missing or empty '{field}'")
    username = record.get("username", "")
    if username and not isinstance(username, str):
        errors.append(f"record[{index}] 'username' must be a string")
    return errors


def main() -> int:
    print("=== R2 to D1 user migration ===\n")

    # 1. Read source
    print(f"Reading R2 object: {USERS_OBJECT_KEY}")
    try:
        source = get_json_object(USERS_OBJECT_KEY)
    except Exception as exc:
        print(f"ERROR: Could not read R2 object: {exc}")
        return 1

    if source is None:
        print(f"ERROR: R2 object '{USERS_OBJECT_KEY}' does not exist.")
        return 1

    if not isinstance(source, list):
        print(f"ERROR: Expected a JSON array in '{USERS_OBJECT_KEY}', got {type(source).__name__}.")
        return 1

    print(f"Found {len(source)} record(s) in source.\n")

    # 2. Validate all records before modifying D1
    all_errors: list[str] = []
    seen_usernames: set[str] = set()
    for i, record in enumerate(source):
        if not isinstance(record, dict):
            all_errors.append(f"record[{i}] is not an object")
            continue
        all_errors.extend(_validate(record, i))
        uname = record.get("username", "").strip().lower()
        if uname in seen_usernames:
            all_errors.append(f"record[{i}] duplicate username '{record.get('username')}'")
        seen_usernames.add(uname)

    if all_errors:
        print("Validation errors found — aborting before any D1 write:\n")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("Validation passed. Importing into D1...\n")

    # 3. Upsert into D1
    inserted = updated = failed = 0
    failures: list[str] = []

    for i, record in enumerate(source):
        username = record["username"].strip()
        password_hash = record["password_hash"]
        is_admin = bool(record.get("is_admin", False))
        is_active = bool(record.get("is_active", True))
        consumer_number = record.get("consumer_number") or None

        try:
            action = db_upsert_user(
                username=username,
                password_hash=password_hash,
                is_admin=is_admin,
                is_active=is_active,
                consumer_number=consumer_number,
            )
            if action == "inserted":
                inserted += 1
            else:
                updated += 1
            print(f"  [{action:8s}] {username}")
        except Exception as exc:
            failed += 1
            failures.append(f"'{username}': {exc}")
            print(f"  [FAILED  ] {username}: {exc}")

    print(f"\nImport complete: {inserted} inserted, {updated} updated, {failed} failed.\n")

    if failed:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")
        return 1

    # 4. Verify imported records
    print("Verifying imported records...\n")
    verify_errors: list[str] = []

    for record in source:
        username = record["username"].strip()
        row = db_get_user(username)
        if row is None:
            verify_errors.append(f"'{username}' not found in D1 after import")
            continue
        if row["password_hash"] != record["password_hash"]:
            verify_errors.append(f"'{username}' password hash mismatch")
        if bool(row["is_admin"]) != bool(record.get("is_admin", False)):
            verify_errors.append(f"'{username}' is_admin mismatch")
        if bool(row["is_active"]) != bool(record.get("is_active", True)):
            verify_errors.append(f"'{username}' is_active mismatch")

    if verify_errors:
        print("Verification FAILED:")
        for err in verify_errors:
            print(f"  - {err}")
        print("\nThe original R2 object has NOT been modified.")
        return 1

    print(f"Verification passed for all {len(source)} record(s).")
    print("\nThe original R2 object login/users.json has NOT been modified.")
    print("Run scripts/cleanup_r2_users.py only after confirming the application works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
