from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from flask import current_app, g
from psycopg import Connection, OperationalError, connect, sql
from psycopg.rows import dict_row
from app.data.content import FORUM_POSTS


def get_db() -> Connection:
    if "db" not in g:
        database_url = current_app.config["DATABASE_URL"]

        try:
            g.db = connect(database_url, row_factory=dict_row)
        except OperationalError as connection_error:
            if not _is_missing_database_error(connection_error):
                raise

            _ensure_database_exists(database_url)
            g.db = connect(database_url, row_factory=dict_row)

    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection:
        connection.close()


def _is_missing_database_error(error):
    message = str(error).lower()
    return "database" in message and "does not exist" in message


def _split_database_url(database_url):
    parts = urlsplit(database_url)
    db_name = parts.path.lstrip("/")

    admin_parts = parts._replace(path="/postgres")
    return urlunsplit(admin_parts), db_name


def _ensure_database_exists(database_url):
    admin_url, db_name = _split_database_url(database_url)

    with connect(admin_url, autocommit=True, row_factory=dict_row) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        ).fetchone()

        if not exists:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
            )


def _time_ago_to_delta(value):
    raw = (value or "").strip().lower()

    if not raw:
        return timedelta(days=1)

    token = raw.split()[0]

    if len(token) < 2:
        return timedelta(days=1)

    amount = int(token[:-1])
    unit = token[-1]

    if unit == "h":
        return timedelta(hours=amount)
    elif unit == "d":
        return timedelta(days=amount)
    elif unit == "w":
        return timedelta(days=amount * 7)

    return timedelta(days=1)


def _seed_forum_posts(connection):
    existing = connection.execute(
        "SELECT COUNT(*) AS total FROM forum_posts"
    ).fetchone()

    if existing and int(existing["total"]) > 0:
        return

    now = datetime.now(timezone.utc)

    for post in FORUM_POSTS:
        created_at = now - _time_ago_to_delta(post.get("time_ago", ""))

        connection.execute(
            """
            INSERT INTO forum_posts
            (author_name, category, title, content, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                post.get("author", "Community member"),
                post.get("category", "General"),
                post.get("title", "Untitled post"),
                post.get("content", ""),
                created_at,
            )
        )


def get_saved_posts_for_user(user_id):
    connection = get_db()

    rows = connection.execute(
        """
        SELECT fp.*
        FROM forum_posts fp
        JOIN user_saved_posts usp
            ON fp.id = usp.post_id
        WHERE usp.user_id = %s
        ORDER BY fp.created_at DESC
        """,
        (user_id,)
    ).fetchall()

    return rows


def init_db():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            interests TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_saved_places (
            user_id BIGINT NOT NULL,
            place_id INTEGER NOT NULL,
            saved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, place_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_saved_events (
            user_id BIGINT NOT NULL,
            event_id INTEGER NOT NULL,
            saved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, event_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
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
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_saved_posts (
            user_id BIGINT NOT NULL,
            post_id BIGINT NOT NULL,
            saved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, post_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
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
    """)

    connection.execute("CREATE INDEX IF NOT EXISTS idx_saved_places_user ON user_saved_places(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_saved_events_user ON user_saved_events(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_saved_posts_user ON user_saved_posts(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_saved_posts_post ON user_saved_posts(post_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_forum_posts_created ON forum_posts(created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_replies_post ON forum_replies(post_id)")

    _seed_forum_posts(connection)

    connection.commit()


def init_db_app(app):
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

def toggle_saved_post(user_id, post_id):
    connection = get_db()

    existing = connection.execute(
        """
        SELECT 1 FROM user_saved_posts
        WHERE user_id = %s AND post_id = %s
        """,
        (user_id, post_id)
    ).fetchone()

    if existing:
        connection.execute(
            """
            DELETE FROM user_saved_posts
            WHERE user_id = %s AND post_id = %s
            """,
            (user_id, post_id)
        )
        connection.commit()
        return False

    connection.execute(
        """
        INSERT INTO user_saved_posts (user_id, post_id)
        VALUES (%s, %s)
        """,
        (user_id, post_id)
    )
    connection.commit()
    return True

def save_user_preferences(user_id, purpose, interests, budget, neighborhoods, social_style):
    connection = get_db()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id BIGINT PRIMARY KEY,
            purpose TEXT,
            interests TEXT,
            budget TEXT,
            neighborhoods TEXT,
            social_style TEXT,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        INSERT INTO user_preferences 
        (user_id, purpose, interests, budget, neighborhoods, social_style)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET
            purpose = EXCLUDED.purpose,
            interests = EXCLUDED.interests,
            budget = EXCLUDED.budget,
            neighborhoods = EXCLUDED.neighborhoods,
            social_style = EXCLUDED.social_style,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            purpose,
            ",".join(interests),
            budget,
            ",".join(neighborhoods),
            social_style,
        )
    )

    connection.commit()


def get_user_preferences(user_id):
    connection = get_db()

    row = connection.execute(
        "SELECT * FROM user_preferences WHERE user_id = %s",
        (user_id,)
    ).fetchone()

    return row