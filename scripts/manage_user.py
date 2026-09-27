#!/usr/bin/env python3
"""
Manage existing users (change username or password).
Run: python scripts/manage_user.py
"""
import sys
import os
import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import hash_password
from app.user_store import get_all_users, update_user


def main():
    users = get_all_users()
    if not users:
        print("No users found. Run scripts/seed_users.py first.")
        return

    print("\nExisting users:")
    for idx, u in enumerate(users, 1):
        status = "active" if u.get("is_active") else "inactive"
        print(f"  {idx}. {u['username']} ({status})")

    print()
    raw = input("Select user (1, 2, or 3): ").strip()
    if raw not in ("1", "2", "3") or int(raw) > len(users):
        print("Invalid selection. Cancelled.")
        return

    user = users[int(raw) - 1]
    old_username = user["username"]
    print(f"\nSelected: {old_username}")
    print("  1. Change username")
    print("  2. Change password")
    print("  3. Change both")
    print("  4. Cancel")

    action = input("\nChoice: ").strip()
    if action not in ("1", "2", "3"):
        print("Cancelled.")
        return

    new_username = None
    new_password_hash = None

    if action in ("1", "3"):
        while True:
            new_username = input("New username: ").strip()
            if not new_username:
                print("Username cannot be empty.")
                continue
            if new_username == old_username:
                print("That is already the current username.")
                continue
            break

    if action in ("2", "3"):
        while True:
            new_password = getpass.getpass("New password: ")
            if not new_password:
                print("Password cannot be empty.")
                continue
            confirm = getpass.getpass("Confirm new password: ")
            if new_password != confirm:
                print("Passwords do not match.")
                continue
            break
        new_password_hash = hash_password(new_password)

    try:
        update_user(old_username, new_username, new_password_hash)
        print("\nChanges saved successfully.")
    except ValueError as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
