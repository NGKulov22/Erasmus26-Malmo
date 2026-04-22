from flask import render_template

from . import main_bp


@main_bp.route("/")
def home():
    return render_template("home.html")


@main_bp.route("/forum")
def forum():
    return render_template("forum.html")



@main_bp.route("/events")
def events():
    return render_template("events.html")

@main_bp.route("/places")
def places():
    return render_template("places.html")

@main_bp.route("/saved")
def saved():
    return render_template("saved.html")


