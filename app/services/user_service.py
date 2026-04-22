from __future__ import annotations

from typing import Sequence

from werkzeug.security import check_password_hash, generate_password_hash

from app.services.db import get_db


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _to_csv(items: Sequence[str]) -> str:
    return ",".join(item.strip().lower() for item in items if item.strip())


def _to_int_csv(items: Sequence[int]) -> str:
    return ",".join(str(item) for item in sorted(set(items)))


def _parse_csv(value: str) -> list[str]:
    if not value:
        return []
    return [item for item in (part.strip() for part in value.split(",")) if item]


def _parse_int_csv(value: str) -> list[int]:
    return [int(item) for item in _parse_csv(value) if item.isdigit()]


def _row_to_user(row) -> dict | None:
    if row is None:
        return None

    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "interests": _parse_csv(row["interests"]),
        "saved_place_ids": _parse_int_csv(row["saved_place_ids"]),
        "created_at": row["created_at"],
    }


def get_user_by_id(user_id: int | None) -> dict | None:
    if user_id is None:
        return None

    row = get_db().execute(
        "SELECT id, full_name, email, interests, saved_place_ids, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return _row_to_user(row)


def get_user_by_email(email: str):
    return get_db().execute("SELECT * FROM users WHERE email = ?", (_normalize_email(email),)).fetchone()


def register_user(full_name: str, email: str, password: str, interests_raw: str) -> tuple[dict | None, str | None]:
    clean_name = full_name.strip()
    clean_email = _normalize_email(email)
    clean_interests = [part.strip() for part in interests_raw.split(",") if part.strip()]

    if not clean_name:
        return None, "Full name is required."
    if "@" not in clean_email:
        return None, "Please provide a valid email address."
    if len(password) < 6:
        return None, "Password must be at least 6 characters."
    if get_user_by_email(clean_email) is not None:
        return None, "Email is already registered."

    connection = get_db()
    connection.execute(
        "INSERT INTO users (full_name, email, password_hash, interests) VALUES (?, ?, ?, ?)",
        (clean_name, clean_email, generate_password_hash(password), _to_csv(clean_interests)),
    )
    connection.commit()

    new_row = connection.execute(
        "SELECT id, full_name, email, interests, saved_place_ids, created_at FROM users WHERE email = ?",
        (clean_email,),
    ).fetchone()

    return _row_to_user(new_row), None


def authenticate_user(email: str, password: str) -> dict | None:
    row = get_user_by_email(email)
    if row is None:
        return None

    if not check_password_hash(row["password_hash"], password):
        return None

    return _row_to_user(row)


def toggle_saved_place(user_id: int, place_id: int) -> bool:
    user = get_user_by_id(user_id)
    if user is None:
        return False

    saved = set(user["saved_place_ids"])
    if place_id in saved:
        saved.remove(place_id)
        is_now_saved = False
    else:
        saved.add(place_id)
        is_now_saved = True

    get_db().execute(
        "UPDATE users SET saved_place_ids = ? WHERE id = ?",
        (_to_int_csv(list(saved)), user_id),
    )
    get_db().commit()
    return is_now_saved
