"""
File-based user store. Users are kept in users.json at the project root.
Format:
[
  {"username": "alice", "password_hash": "...", "is_active": true},
  ...
]
Exactly 3 users are enforced by the seed/manage scripts.
"""
import json
import os
from typing import Optional

USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "users.json")


def _load() -> list[dict]:
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(users: list[dict]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def get_all_users() -> list[dict]:
    return _load()


def get_user(username: str) -> Optional[dict]:
    for u in _load():
        if u["username"] == username:
            return u
    return None


def count_users() -> int:
    return len(_load())


def create_user(username: str, password_hash: str) -> None:
    users = _load()
    if len(users) >= 3:
        raise ValueError("3 users already exist.")
    if any(u["username"] == username for u in users):
        raise ValueError(f"Username '{username}' already exists.")
    users.append({"username": username, "password_hash": password_hash, "is_active": True})
    _save(users)


def get_user_by_consumer_number(consumer_number: str) -> Optional[dict]:
    for u in _load():
        if u.get("consumer_number") == consumer_number:
            return u
    return None


def update_user_consumer_number(username: str, consumer_number: str) -> None:
    users = _load()
    for u in users:
        if u["username"] == username:
            u["consumer_number"] = consumer_number
            _save(users)
            return
    raise ValueError(f"User '{username}' not found.")


def update_user(old_username: str, new_username: Optional[str], new_password_hash: Optional[str]) -> None:
    users = _load()
    if new_username and new_username != old_username:
        if any(u["username"] == new_username for u in users):
            raise ValueError(f"Username '{new_username}' already exists.")
    for u in users:
        if u["username"] == old_username:
            if new_username:
                u["username"] = new_username
            if new_password_hash:
                u["password_hash"] = new_password_hash
            _save(users)
            return
    raise ValueError(f"User '{old_username}' not found.")
