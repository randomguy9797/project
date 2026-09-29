from typing import Optional

from app.storage import USERS_OBJECT_KEY, get_json_object, put_json_object


def _load() -> list[dict]:
    users = get_json_object(USERS_OBJECT_KEY)
    if users is None:
        return []
    if not isinstance(users, list) or not all(isinstance(user, dict) for user in users):
        raise RuntimeError("Authentication users data in R2 has an invalid structure.")
    return users


def _save(users: list[dict]) -> None:
    put_json_object(USERS_OBJECT_KEY, users)


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


def update_user_consumer_number(username: str, consumer_number: str) -> None:
    """Retain the existing management-script operation in the R2 user store."""
    users = _load()
    for user in users:
        if user["username"] == username:
            user["consumer_number"] = consumer_number
            _save(users)
            return
    raise ValueError(f"User '{username}' not found.")
