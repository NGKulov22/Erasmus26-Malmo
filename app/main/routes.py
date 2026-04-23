from flask import flash, g, redirect, render_template, request, url_for

from app.services.content_service import (
    get_events,
    get_forum_categories,
    get_forum_posts,
    get_place_by_id,
    get_place_categories,
    get_places,
    get_places_by_ids,
    get_recommended_places,
)
from app.services.user_service import toggle_saved_place
from app.utils.auth import login_required
from . import main_bp


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


@main_bp.route("/events")
def events():
    return render_template("events.html", events=get_events())


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
    saved_places = get_places_by_ids(g.current_user["saved_place_ids"])
    suggested_places = get_recommended_places(g.current_user["interests"], limit=3)
    return render_template(
        "saved.html",
        saved_places=saved_places,
        suggested_places=suggested_places,
    )


