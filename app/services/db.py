from datetime import datetime, timedelta, timezone

from flask import current_app, g
from psycopg import Connection, connect
from psycopg.rows import dict_row

from app.data.content import FORUM_POSTS


def _time_ago_to_delta(value: str) -> timedelta:
    raw = (value or "").strip().lower()
    if not raw:
        return timedelta(days=1)

    token = raw.split()[0]
    if len(token) < 2 or not token[:-1].isdigit():
        return timedelta(days=1)

    amount = int(token[:-1])
    unit = token[-1]

    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(days=amount * 7)

    return timedelta(days=1)


def _seed_forum_posts(connection: Connection) -> None:
    existing = connection.execute("SELECT COUNT(*) AS total FROM forum_posts").fetchone()
    if existing and int(existing["total"]) > 0:
        return

    now = datetime.now(timezone.utc)
    for post in FORUM_POSTS:
        created_at = now - _time_ago_to_delta(post.get("time_ago", ""))
        connection.execute(
            """
            INSERT INTO forum_posts (author_name, category, title, content, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                post.get("author", "Community member"),
                post.get("category", "General"),
                post.get("title", "Untitled post"),
                post.get("content", ""),
                created_at,
            ),
        )


def get_db() -> Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_URL"], row_factory=dict_row)

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
            id BIGSERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            interests TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_saved_places (
            user_id BIGINT NOT NULL,
            place_id INTEGER NOT NULL,
            saved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, place_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS forum_posts (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT,
            author_name TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS forum_replies (
            id BIGSERIAL PRIMARY KEY,
            post_id BIGINT NOT NULL,
            user_id BIGINT,
            author_name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
    _seed_forum_posts(connection)
    connection.commit()


def init_db_app(app) -> None:
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
