from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import flash, g, redirect, request, url_for


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped_view(*args: Any, **kwargs: Any):
        if getattr(g, "current_user", None) is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth_bp.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view
