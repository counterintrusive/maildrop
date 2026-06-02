import logging
import time
from flask import Blueprint, render_template, request, jsonify, session, g, redirect, url_for
from .. import user_store
from ..auth import login_required

logger = logging.getLogger("maildrop")

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Per-IP rate limiter for auth endpoints (login/register)
class _AuthRateLimiter:
    def __init__(self, limit: int = 10, window: int = 60):
        self.limit = limit
        self.window = window
        self._attempts: dict[str, list[float]] = {}

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        timestamps = self._attempts.get(ip, [])
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= self.limit:
            self._attempts[ip] = timestamps
            return False
        timestamps.append(now)
        self._attempts[ip] = timestamps
        return True

_auth_limiter = _AuthRateLimiter(limit=10, window=60)


@bp.after_request
def log_after_request(response):
    logger.info(f"Auth Request | {request.remote_addr} | {request.method} | {request.path} | Status: {response.status}")
    return response


# --- Page routes ---

@bp.route('/login')
def login_page():
    """Render the login page."""
    if session.get("user_id"):
        return redirect(url_for("pages.index"))
    return render_template('login.html')


@bp.route('/register')
def register_page():
    """Render the registration page."""
    if session.get("user_id"):
        return redirect(url_for("pages.index"))
    return render_template('register.html')


@bp.route('/logout')
def logout():
    """Log out and redirect to the main page."""
    session.clear()
    # Create a new session to prevent session fixation
    session.cycle_key() if hasattr(session, 'cycle_key') else None
    return redirect(url_for("pages.index"))


# --- API routes (no /api/ prefix — /auth/login, /auth/register, etc.) ---

@bp.route('/login', methods=['POST'])
def api_login():
    """Authenticate a user and create a session."""
    # Rate limit
    if not _auth_limiter.allow(request.remote_addr):
        logger.warning(f"Rate limit exceeded for login from {request.remote_addr}")
        return jsonify({"error": "Too many attempts. Try again later."}), 429

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user_id = user_store.authenticate_user(email, password)
    if user_id is None:
        return jsonify({"error": "Invalid email or password"}), 401

    # Clear any existing session data before setting user_id (prevents session fixation)
    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    user = user_store.get_user_by_id(user_id)

    keys = user_store.get_user_keys(user_id)

    logger.info(f"User {user_id} ({email}) logged in")
    return jsonify({
        "message": "Logged in",
        "user": {"id": user["id"], "email": user["email"]},
        "has_api_key": len(keys) > 0,
    }), 200


@bp.route('/register', methods=['POST'])
def api_register():
    """Register a new user and create a session + API key."""
    # Rate limit
    if not _auth_limiter.allow(request.remote_addr):
        logger.warning(f"Rate limit exceeded for register from {request.remote_addr}")
        return jsonify({"error": "Too many attempts. Try again later."}), 429

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if "@" not in email or "." not in email:
        return jsonify({"error": "Invalid email address"}), 400

    try:
        user_id = user_store.create_user(email, password)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    # Auto-generate an API key for the new user
    try:
        api_key = user_store.generate_api_key(user_id)
    except ValueError:
        api_key = None

    # Clear any existing session data before setting user_id (prevents session fixation)
    session.clear()
    session["user_id"] = user_id
    session.permanent = True

    logger.info(f"User {user_id} ({email}) registered")
    return jsonify({
        "message": "Registered successfully",
        "api_key": api_key,
        "user": {"id": user_id, "email": email},
    }), 201


@bp.route('/logout', methods=['POST'])
def api_logout():
    """Clear the session."""
    session.clear()
    return jsonify({"message": "Logged out"}), 200


@bp.route('/me', methods=['GET'])
def api_me():
    """Return the current user's info if logged in, or 401."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    user = user_store.get_user_by_id(user_id)
    if user is None:
        session.clear()
        return jsonify({"error": "User not found"}), 401

    keys = user_store.get_user_keys(user_id)
    return jsonify({
        "user": user,
        "has_api_key": len(keys) > 0,
        "keys": keys,
    }), 200
