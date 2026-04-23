import sqlite3
from pathlib import Path

from flask import current_app, g

from app.data.content import FORUM_POSTS


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


def _time_ago_to_sqlite_modifier(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return "-1 day"

    token = raw.split()[0]
    if len(token) < 2 or not token[:-1].isdigit():
        return "-1 day"

    amount = int(token[:-1])
    unit = token[-1]

    if unit == "h":
        return f"-{amount} hours"
    if unit == "d":
        return f"-{amount} days"
    if unit == "w":
        return f"-{amount * 7} days"

    return "-1 day"


def _seed_forum_posts(connection: sqlite3.Connection) -> None:
    existing = connection.execute("SELECT COUNT(*) AS total FROM forum_posts").fetchone()
    if existing and int(existing["total"]) > 0:
        return

    for post in FORUM_POSTS:
        modifier = _time_ago_to_sqlite_modifier(post.get("time_ago", ""))
        connection.execute(
            """
            INSERT INTO forum_posts (author_name, category, title, content, created_at)
            VALUES (?, ?, ?, ?, datetime('now', ?))
            """,
            (
                post.get("author", "Community member"),
                post.get("category", "General"),
                post.get("title", "Untitled post"),
                post.get("content", ""),
                modifier,
            ),
        )


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
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS forum_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            author_name TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS forum_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER,
            author_name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_user_saved_places_user ON user_saved_places(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_user_saved_places_place ON user_saved_places(place_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_forum_posts_category ON forum_posts(category)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_forum_posts_created_at ON forum_posts(created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_forum_replies_post_id ON forum_replies(post_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_forum_replies_created_at ON forum_replies(created_at)")
    _migrate_legacy_saved_places(connection)
    _seed_forum_posts(connection)
    connection.commit()


def init_db_app(app) -> None:
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
