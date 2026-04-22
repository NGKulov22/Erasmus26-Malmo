from flask import flash, g, redirect, render_template, request, session, url_for

from app.services.user_service import authenticate_user, register_user
from app.utils.auth import login_required
from . import auth_bp


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.current_user:
        return redirect(url_for("main_bp.home"))

    next_page = request.args.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        next_page = request.form.get("next", "")

        user = authenticate_user(email=email, password=password)
        if not user:
            flash("Invalid email or password.", "error")
            return render_template("login.html", next_page=next_page)

        session["user_id"] = user["id"]
        flash(f"Welcome back, {user['full_name']}.", "success")
        if next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("main_bp.home"))

    return render_template("login.html", next_page=next_page)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if g.current_user:
        return redirect(url_for("main_bp.home"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        interests = request.form.get("interests", "")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        user, error = register_user(
            full_name=full_name,
            email=email,
            password=password,
            interests_raw=interests,
        )
        if error:
            flash(error, "error")
            return render_template("register.html")

        session["user_id"] = user["id"]
        flash("Registration successful.", "success")
        return redirect(url_for("main_bp.home"))

    return render_template("register.html")


@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=g.current_user)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("main_bp.home"))

