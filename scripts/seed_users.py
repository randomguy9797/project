#!/usr/bin/env python3
"""
Seed the initial 3 users into R2 at login/users.json.
Run: python scripts/seed_users.py
"""
import sys
import os
import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import hash_password
from app.user_store import count_users, create_user, get_all_users


def main():
    existing = count_users()
    if existing >= 3:
        print("3 users already exist. Use scripts/manage_user.py to change them.")
        return

    print("Creating 3 users.\n")
    needed = 3 - existing

    for i in range(existing + 1, existing + needed + 1):
        while True:
            username = input(f"Username for user {i}: ").strip()
            if not username:
                print("Username cannot be empty.")
                continue
            if any(u["username"] == username for u in get_all_users()):
                print("Username already exists.")
                continue
            break

        while True:
            password = getpass.getpass(f"Password for user {i}: ")
            if not password:
                print("Password cannot be empty.")
                continue
            confirm = getpass.getpass(f"Confirm password for user {i}: ")
            if password != confirm:
                print("Passwords do not match.")
                continue
            break

        create_user(username, hash_password(password))
        print(f"User {i} created.\n")

    print("All 3 users created successfully.")


if __name__ == "__main__":
    main()
