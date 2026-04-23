from __future__ import annotations

from app.data.content import EVENTS, FORUM_POSTS, PLACES


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


def get_forum_categories() -> list[str]:
    categories = sorted({post["category"].lower() for post in FORUM_POSTS})
    return ["all", *categories]


def get_forum_posts(search: str = "", category: str = "all", sort: str = "hot") -> list[dict]:
    query = search.strip().lower()
    selected = category.strip().lower() or "all"
    selected_sort = sort.strip().lower() or "hot"

    posts = FORUM_POSTS
    if selected != "all":
        posts = [post for post in posts if post["category"].lower() == selected]

    if query:
        posts = [
            post
            for post in posts
            if query in post["title"].lower()
            or query in post["content"].lower()
            or query in post["author"].lower()
            or query in post["category"].lower()
        ]

    if selected_sort == "new":
        return sorted(posts, key=lambda post: _time_ago_to_hours(post.get("time_ago", "")))

    if selected_sort == "top":
        return sorted(posts, key=lambda post: post.get("replies", 0), reverse=True)

    def hot_score(post: dict) -> float:
        hours_old = _time_ago_to_hours(post.get("time_ago", ""))
        return (post.get("replies", 0) * 2) - (min(hours_old, 72) * 0.2)

    return sorted(posts, key=hot_score, reverse=True)


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
