import functools
import logging
from flask import request, jsonify, g, session
from . import user_store

logger = logging.getLogger("maildrop")


def require_api_key(f):
    """Decorator that requires a valid API key in the Authorization header.

    On success sets g.user_id to the authenticated user's ID.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401

        raw_key = auth[len("Bearer "):].strip()
        user_id = user_store.lookup_user_by_key(raw_key)
        if user_id is None:
            return jsonify({"error": "Unauthorized"}), 401

        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated


def login_optional(f):
    """Decorator that sets g.user_id from the session if logged in.

    Does NOT require authentication — guests can still access the route.
    g.user_id will be None for unauthenticated requests.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        g.user_id = user_id if user_id else None
        return f(*args, **kwargs)
    return decorated


def login_required(f):
    """Decorator that requires an active session (web login).

    Redirects to /login for HTML requests, returns 401 for API requests.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            # If the client expects JSON, return 401
            if request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json":
                return jsonify({"error": "Unauthorized"}), 401
            from flask import redirect, url_for
            return redirect(url_for("auth.login_page"))
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated
