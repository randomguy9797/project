#!/usr/bin/env python3
"""
Delete login/users.json from R2 after the D1 migration has been verified.

This script is intentionally separate and requires explicit confirmation.
Do NOT run this until:
  1. migrate_users_r2_to_d1.py has completed successfully.
  2. Login, logout, and admin user-management have been tested against D1.
  3. You are certain the application no longer reads login/users.json.

Usage:
    python scripts/cleanup_r2_users.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage import get_json_object, USERS_OBJECT_KEY
from app.d1 import db_get_all_users


def main() -> int:
    print("=== R2 users.json cleanup ===\n")
    print("WARNING: This will permanently delete the R2 object:")
    print(f"  {USERS_OBJECT_KEY}\n")

    # Verify D1 has users before allowing deletion
    print("Checking D1 user count...")
    try:
        d1_users = db_get_all_users()
    except Exception as exc:
        print(f"ERROR: Could not query D1: {exc}")
        print("Aborting. The R2 object has NOT been deleted.")
        return 1

    if not d1_users:
        print("ERROR: D1 contains no users. Aborting to prevent data loss.")
        return 1

    print(f"D1 contains {len(d1_users)} user(s): {[u['username'] for u in d1_users]}\n")

    # Verify R2 object still exists
    print(f"Checking R2 object '{USERS_OBJECT_KEY}'...")
    try:
        source = get_json_object(USERS_OBJECT_KEY)
    except Exception as exc:
        print(f"ERROR: Could not read R2 object: {exc}")
        return 1

    if source is None:
        print("R2 object does not exist — nothing to delete.")
        return 0

    r2_count = len(source) if isinstance(source, list) else "unknown"
    print(f"R2 object exists with {r2_count} record(s).\n")

    confirm = input(
        f"Type 'DELETE' to permanently remove '{USERS_OBJECT_KEY}' from R2: "
    ).strip()
    if confirm != "DELETE":
        print("Cancelled. The R2 object has NOT been deleted.")
        return 0

    # Import here to avoid importing storage delete at module level
    from app.storage import _delete_object  # noqa: PLC0415
    try:
        _delete_object(USERS_OBJECT_KEY)
    except Exception as exc:
        print(f"ERROR: Delete failed: {exc}")
        return 1

    print(f"\nDeleted '{USERS_OBJECT_KEY}' from R2 successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
