from __future__ import annotations

from typing import Sequence

from werkzeug.security import check_password_hash, generate_password_hash

from app.services.db import get_db


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _to_csv(items: Sequence[str]) -> str:
    return ",".join(item.strip().lower() for item in items if item.strip())


def _parse_csv(value: str) -> list[str]:
    if not value:
        return []
    return [item for item in (part.strip() for part in value.split(",")) if item]


def _get_saved_place_ids(user_id: int) -> list[int]:
    rows = get_db().execute(
        "SELECT place_id FROM user_saved_places WHERE user_id = %s ORDER BY place_id",
        (user_id,),
    ).fetchall()
    return [int(row["place_id"]) for row in rows]


def _row_to_user(row) -> dict | None:
    if row is None:
        return None

    user_id = int(row["id"])

    return {
        "id": user_id,
        "full_name": row["full_name"],
        "email": row["email"],
        "interests": _parse_csv(row["interests"]),
        "saved_place_ids": _get_saved_place_ids(user_id),
        "created_at": row["created_at"],
    }


def get_user_by_id(user_id: int | None) -> dict | None:
    if user_id is None:
        return None

    row = get_db().execute(
        "SELECT id, full_name, email, interests, created_at FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()
    return _row_to_user(row)


def get_user_by_email(email: str):
    return get_db().execute("SELECT * FROM users WHERE email = %s", (_normalize_email(email),)).fetchone()


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
        "INSERT INTO users (full_name, email, password_hash, interests) VALUES (%s, %s, %s, %s)",
        (clean_name, clean_email, generate_password_hash(password), _to_csv(clean_interests)),
    )
    connection.commit()

    new_row = connection.execute(
        "SELECT id, full_name, email, interests, created_at FROM users WHERE email = %s",
        (clean_email,),
    ).fetchone()

    return _row_to_user(new_row), None


def authenticate_user(email: str, password: str) -> dict | None:
    row = get_user_by_email(email)
    if row is None:
        return None

    if not check_password_hash(row["password_hash"], password):
        return None

    return get_user_by_id(int(row["id"]))


def toggle_saved_place(user_id: int, place_id: int) -> bool:
    if get_user_by_id(user_id) is None:
        return False

    connection = get_db()
    existing = connection.execute(
        "SELECT 1 FROM user_saved_places WHERE user_id = %s AND place_id = %s",
        (user_id, place_id),
    ).fetchone()

    if existing:
        connection.execute(
            "DELETE FROM user_saved_places WHERE user_id = %s AND place_id = %s",
            (user_id, place_id),
        )
        connection.commit()
        return False

    connection.execute(
        "INSERT INTO user_saved_places (user_id, place_id) VALUES (%s, %s)",
        (user_id, place_id),
    )
    connection.commit()
    return True
