from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.data.content import EVENTS, PLACES
from app.services.db import get_db


def get_places(search: str = "", category: str = "all") -> list[dict]:
    query = search.strip().lower()
    selected = category.strip().lower() or "all"

    places = PLACES
    if selected != "all":
        places = [place for place in places if place["category"].lower() == selected]

    if query:
        places = [
            place
            for place in places
            if query in place["name"].lower()
            or query in place["location"].lower()
            or any(query in tag.lower() for tag in place["tags"])
        ]

    return sorted(places, key=lambda place: place["rating"], reverse=True)


def get_place_categories() -> list[str]:
    categories = sorted({place["category"] for place in PLACES})
    return ["all", *categories]


def get_place_by_id(place_id: int) -> dict | None:
    return next((place for place in PLACES if place["id"] == place_id), None)


def get_places_by_ids(place_ids: list[int]) -> list[dict]:
    by_id = {place["id"]: place for place in PLACES}
    return [by_id[pid] for pid in place_ids if pid in by_id]


def get_events() -> list[dict]:
    return EVENTS


def _time_ago_to_hours(value: str) -> int:
    parts = value.strip().split()
    if len(parts) < 2:
        return 10**9

    try:
        amount = int(parts[0])
    except ValueError:
        return 10**9

    unit = parts[1].lower()
    if unit.startswith("h"):
        return amount
    if unit.startswith("d"):
        return amount * 24
    if unit.startswith("w"):
        return amount * 24 * 7

    return 10**9


def _parse_datetime(value: datetime | str | None) -> datetime:
    if isinstance(value, datetime):
        return value

    normalized = (value or "").strip().replace(" ", "T")
    if not normalized:
        return datetime.now(timezone.utc)

    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _hours_since(timestamp: datetime | str | None) -> float:
    created_at = _parse_datetime(timestamp)
    now = datetime.now(timezone.utc)
    delta = now - created_at
    return max(delta.total_seconds() / 3600.0, 0.0)


def _time_ago_from_timestamp(timestamp: datetime | str | None) -> str:
    seconds = int(_hours_since(timestamp) * 3600)
    if seconds < 60:
        return "just now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"

    days = hours // 24
    if days < 7:
        return f"{days}d ago"

    weeks = max(days // 7, 1)
    return f"{weeks}w ago"


def _reply_rows_by_post_ids(post_ids: list[int]) -> dict[int, list[dict]]:
    if not post_ids:
        return {}

    placeholders = ",".join("%s" for _ in post_ids)
    rows = get_db().execute(
        f"""
        SELECT post_id, author_name, content, created_at
        FROM forum_replies
        WHERE post_id IN ({placeholders})
        ORDER BY created_at ASC
        """,
        tuple(post_ids),
    ).fetchall()

    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[int(row["post_id"])].append(
            {
                "author": row["author_name"],
                "content": row["content"],
                "time_ago": _time_ago_from_timestamp(row["created_at"]),
            }
        )

    return grouped


def get_forum_categories() -> list[str]:
    rows = get_db().execute("SELECT DISTINCT category FROM forum_posts").fetchall()
    categories = sorted({str(row["category"]).strip().lower() for row in rows if str(row["category"]).strip()})
    return ["all", *categories]


def get_forum_posts(search: str = "", category: str = "all", sort: str = "hot") -> list[dict]:
    query = search.strip().lower()
    selected = category.strip().lower() or "all"
    selected_sort = sort.strip().lower() or "hot"

    rows = get_db().execute(
        """
        SELECT
            p.id,
            p.author_name,
            p.category,
            p.title,
            p.content,
            p.created_at,
            COUNT(r.id) AS replies
        FROM forum_posts AS p
        LEFT JOIN forum_replies AS r ON r.post_id = p.id
        GROUP BY p.id
        """
    ).fetchall()

    posts: list[dict] = []
    for row in rows:
        post = {
            "id": int(row["id"]),
            "author": row["author_name"],
            "title": row["title"],
            "content": row["content"],
            "category": row["category"],
            "replies": int(row["replies"] or 0),
            "created_at": row["created_at"],
        }

        if selected != "all" and post["category"].strip().lower() != selected:
            continue

        if query and not (
            query in post["title"].lower()
            or query in post["content"].lower()
            or query in post["author"].lower()
            or query in post["category"].lower()
        ):
            continue

        posts.append(post)

    reply_map = _reply_rows_by_post_ids([post["id"] for post in posts])
    for post in posts:
        post["time_ago"] = _time_ago_from_timestamp(post["created_at"])
        post["reply_items"] = reply_map.get(post["id"], [])

    if selected_sort == "new":
        return sorted(posts, key=lambda post: _parse_datetime(post["created_at"]), reverse=True)

    if selected_sort == "top":
        return sorted(
            posts,
            key=lambda post: (post.get("replies", 0), _parse_datetime(post["created_at"])),
            reverse=True,
        )

    def hot_score(post: dict) -> float:
        hours_old = _hours_since(post.get("created_at", ""))
        return (post.get("replies", 0) * 2) - (min(hours_old, 72) * 0.2)

    return sorted(posts, key=hot_score, reverse=True)


def create_forum_post(user_id: int, author_name: str, title: str, category: str, content: str) -> str | None:
    clean_title = title.strip()
    clean_category = category.strip()
    clean_content = content.strip()

    if not clean_title:
        return "Post title is required."
    if not clean_category:
        return "Topic is required."
    if not clean_content:
        return "Post content is required."
    if len(clean_title) > 120:
        return "Title is too long (max 120 characters)."
    if len(clean_category) > 40:
        return "Topic is too long (max 40 characters)."
    if len(clean_content) > 2000:
        return "Post is too long (max 2000 characters)."

    connection = get_db()
    connection.execute(
        """
        INSERT INTO forum_posts (user_id, author_name, category, title, content)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, author_name, clean_category, clean_title, clean_content),
    )
    connection.commit()
    return None


def create_forum_reply(user_id: int, post_id: int, author_name: str, content: str) -> str | None:
    clean_content = content.strip()
    if not clean_content:
        return "Reply cannot be empty."
    if len(clean_content) > 280:
        return "Reply is too long (max 280 characters)."

    connection = get_db()
    exists = connection.execute("SELECT 1 FROM forum_posts WHERE id = %s", (post_id,)).fetchone()
    if exists is None:
        return "Post not found."

    connection.execute(
        """
        INSERT INTO forum_replies (post_id, user_id, author_name, content)
        VALUES (%s, %s, %s, %s)
        """,
        (post_id, user_id, author_name, clean_content),
    )
    connection.commit()
    return None


def get_recommended_places(interests: list[str], limit: int = 6) -> list[dict]:
    if not interests:
        return get_places()[:limit]

    interest_set = {item.lower() for item in interests}
    scored: list[tuple[int, dict]] = []

    for place in PLACES:
        tokens = {place["category"].lower(), *[tag.lower() for tag in place["tags"]]}
        score = len(tokens.intersection(interest_set))
        scored.append((score, place))

    scored.sort(key=lambda item: (item[0], item[1]["rating"]), reverse=True)
    picks = [place for score, place in scored if score > 0]
    if not picks:
        return get_places()[:limit]

    return picks[:limit]
