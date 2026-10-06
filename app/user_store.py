"""
User store — backed by Cloudflare D1.

Public API is identical to the previous R2-backed version so that no
route handler or script needs to change.
"""
from typing import Optional

from app.d1 import (
    db_get_user,
    db_get_all_users,
    db_create_user,
    db_update_user,
    db_delete_user,
    db_update_consumer_number,
)


def get_all_users() -> list[dict]:
    return db_get_all_users()


def get_user(username: str) -> Optional[dict]:
    return db_get_user(username)


def count_users() -> int:
    return len(db_get_all_users())


def create_user(username: str, password_hash: str, is_admin: bool = False) -> None:
    db_create_user(username, password_hash, is_admin)


def update_user(
    old_username: str,
    new_username: Optional[str],
    new_password_hash: Optional[str],
) -> None:
    db_update_user(old_username, new_username, new_password_hash)


def delete_user(username: str) -> None:
    db_delete_user(username)


def update_user_consumer_number(username: str, consumer_number: str) -> None:
    db_update_consumer_number(username, consumer_number)
