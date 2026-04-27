from flask import flash, g, redirect, render_template, request, url_for

from app.services.content_service import (
    create_forum_post,
    create_forum_reply,
    get_events,
    get_event_by_id,
    get_events_by_ids,
    get_forum_categories,
    get_forum_posts,
    get_place_by_id,
    get_place_categories,
    get_places,
    get_places_by_ids,
    get_recommended_places,
)
from app.services.user_service import toggle_saved_place, toggle_saved_event
from app.utils.auth import login_required
from . import main_bp
from ..services.db import get_saved_posts_for_user


def _forum_redirect_target() -> str:
    query = request.form.get("q", "").strip()
    category = (request.form.get("category", "all") or "all").strip().lower()
    sort = (request.form.get("sort", "hot") or "hot").strip().lower()
    return url_for("main_bp.forum", q=query, category=category, sort=sort)


@main_bp.route("/")
def home():
    return render_template("home.html")


@main_bp.route("/recommendations")
def recommendations():
    interests = g.current_user["interests"] if g.current_user else []
    places = get_recommended_places(interests)
    return render_template("recommendations.html", places=places, interests=interests)


@main_bp.route("/forum")
def forum():
    query = request.args.get("q", "").strip()
    category = (request.args.get("category", "all") or "all").strip().lower()
    sort = (request.args.get("sort", "hot") or "hot").strip().lower()

    return render_template(
        "forum.html",
        posts=get_forum_posts(search=query, category=category, sort=sort),
        categories=get_forum_categories(),
        selected_category=category,
        selected_sort=sort,
        query=query,
    )


@main_bp.route("/forum/posts", methods=["POST"])
@login_required
def forum_create_post():
    error = create_forum_post(
        user_id=g.current_user["id"],
        author_name=g.current_user["full_name"],
        title=request.form.get("title", ""),
        category=request.form.get("topic", ""),
        content=request.form.get("content", ""),
    )

    if error:
        flash(error, "error")
    else:
        flash("Post published.", "success")

    return redirect(_forum_redirect_target())


@main_bp.route("/forum/posts/<int:post_id>/replies", methods=["POST"])
@login_required
def forum_create_reply(post_id: int):
    error = create_forum_reply(
        user_id=g.current_user["id"],
        post_id=post_id,
        author_name=g.current_user["full_name"],
        content=request.form.get("content", ""),
    )

    if error:
        flash(error, "error")
    else:
        flash("Reply posted.", "success")

    return redirect(_forum_redirect_target())


@main_bp.route("/events")
def events():
    saved_ids = set(g.current_user.get("saved_event_ids", [])) if g.current_user else set()
    return render_template("events.html", events=get_events(), saved_ids=saved_ids)


@main_bp.route("/events/<int:event_id>/toggle-save", methods=["POST"])
@login_required
def toggle_event_save(event_id: int):
    if get_event_by_id(event_id) is None:
        flash("Event not found.", "error")
        return redirect(url_for("main_bp.events"))

    is_saved = toggle_saved_event(g.current_user["id"], event_id)
    flash("Event saved." if is_saved else "Event removed from saved.", "success")
    return redirect(request.referrer or url_for("main_bp.events"))


@main_bp.route("/places")
def places():
    query = request.args.get("q", "").strip()
    category = (request.args.get("category", "all") or "all").strip().lower()

    places_list = get_places(search=query, category=category)
    saved_ids = set(g.current_user["saved_place_ids"]) if g.current_user else set()

    return render_template(
        "places.html",
        places=places_list,
        categories=get_place_categories(),
        selected_category=category,
        query=query,
        saved_ids=saved_ids,
    )


@main_bp.route("/places/<int:place_id>/toggle-save", methods=["POST"])
@login_required
def toggle_place_save(place_id: int):
    if get_place_by_id(place_id) is None:
        flash("Place not found.", "error")
        return redirect(url_for("main_bp.places"))

    is_saved = toggle_saved_place(g.current_user["id"], place_id)
    flash("Place saved." if is_saved else "Place removed from saved.", "success")
    return redirect(request.referrer or url_for("main_bp.places"))


@main_bp.route("/saved")
@login_required
def saved():
    saved_places = get_places_by_ids(g.current_user.get("saved_place_ids", []))
    saved_events = get_events_by_ids(g.current_user.get("saved_event_ids", []))
    saved_posts = get_saved_posts_for_user(g.current_user["id"])
    suggested_places = get_recommended_places(g.current_user["interests"], limit=3)
    return render_template(
        "saved.html",
        saved_places=saved_places,
        saved_events=saved_events,
        saved_posts=saved_posts,
        suggested_places=suggested_places
    )
@main_bp.route("/saved-events")
def saved_events():
    return render_template("savedEvents.html")

@main_bp.route("/posts/<int:post_id>/toggle-save", methods=["POST"])
@login_required
def toggle_post_save(post_id):
    from app.services.db import toggle_saved_post

    is_saved = toggle_saved_post(g.current_user["id"], post_id)

    flash("Post saved." if is_saved else "Post removed.", "success")

    return redirect(request.referrer or url_for("main_bp.forum"))
