import logging
import os
from flask import Flask
from .routes import pages, api, auth
import config

logger = logging.getLogger("maildrop")

# Resolve template/static paths relative to this file's location
_basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__,
            template_folder=os.path.join(_basedir, '..', 'frontend', 'templates'),
            static_folder=os.path.join(_basedir, '..', 'frontend', 'static'))

# Set a secret key for session signing (L3)
if config.settings.FLASK_SECRET_KEY:
    app.secret_key = config.settings.FLASK_SECRET_KEY
else:
    # Fallback: generate a random key each startup (invalidates sessions on restart)
    import secrets
    app.secret_key = secrets.token_hex(32)
    logger.warning("FLASK_SECRET_KEY not set — using ephemeral key (sessions invalidated on restart)")

# Session config
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 30  # 30 days
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.register_blueprint(pages.bp) # load the blueprint for the all of the main web page routes
app.register_blueprint(api.bp) # load the blueprint for the all of the api routes
app.register_blueprint(auth.bp) # load the blueprint for the auth routes


# Security headers (L2)
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # CSP — allow inline scripts on auth pages (login/register have inline JS)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# disable flask's logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Runs the main flask app
def run_flask_server(host, port):
    logger.info(f"Starting Flask server on {host}:{port}")
    app.run(host=host, port=port, debug=False)