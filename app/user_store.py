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


def create_user(username: str, password_hash: str, is_admin: bool = False) -> None:
    users = _load()
    if any(u["username"] == username for u in users):
        raise ValueError(f"Username '{username}' already exists.")
    users.append({
        "username": username,
        "password_hash": password_hash,
        "is_active": True,
        "is_admin": is_admin,
    })
    _save(users)


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


def delete_user(username: str) -> None:
    users = _load()
    new_users = [u for u in users if u["username"] != username]
    if len(new_users) == len(users):
        raise ValueError(f"User '{username}' not found.")
    _save(new_users)
