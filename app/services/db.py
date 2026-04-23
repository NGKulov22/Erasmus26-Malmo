import sqlite3
from pathlib import Path

from flask import current_app, g


def _parse_legacy_int_csv(value: str) -> list[int]:
    if not value:
        return []

    ids: list[int] = []
    for raw_item in value.split(","):
        item = raw_item.strip()
        if item.isdigit():
            ids.append(int(item))
    return ids


def _migrate_legacy_saved_places(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
    if "saved_place_ids" not in columns:
        return

    rows = connection.execute(
        "SELECT id, saved_place_ids FROM users WHERE saved_place_ids IS NOT NULL AND saved_place_ids != ''"
    ).fetchall()

    for row in rows:
        for place_id in _parse_legacy_int_csv(row["saved_place_ids"]):
            connection.execute(
                "INSERT OR IGNORE INTO user_saved_places (user_id, place_id) VALUES (?, ?)",
                (row["id"], place_id),
            )

    connection.execute("UPDATE users SET saved_place_ids = '' WHERE saved_place_ids IS NOT NULL AND saved_place_ids != ''")

    # Best-effort cleanup for modern SQLite versions.
    try:
        connection.execute("ALTER TABLE users DROP COLUMN saved_place_ids")
    except sqlite3.OperationalError:
        # Some SQLite builds do not support DROP COLUMN.
        pass


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = Path(current_app.config["DATABASE"])
        db_path.parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection

    return g.db


def close_db(_error: Exception | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    connection = get_db()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            interests TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_saved_places (
            user_id INTEGER NOT NULL,
            place_id INTEGER NOT NULL,
            saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, place_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_user_saved_places_user ON user_saved_places(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_user_saved_places_place ON user_saved_places(place_id)")
    _migrate_legacy_saved_places(connection)
    connection.commit()


def init_db_app(app) -> None:
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
