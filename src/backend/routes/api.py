from flask import Blueprint, render_template, request, jsonify
from .. import inbox_handler
from .. import sender
import config
import re
import secrets
import string
import logging
from urllib.parse import urlparse

logger = logging.getLogger("maildrop")

bp = Blueprint('api', __name__)

# Log API requests
@bp.after_request
def log_after_request(response):
    logger.info(f"API Request | {request.remote_addr} | {request.method} | {request.path} | Status: {response.status}")
    return response


def _origin_allowed() -> bool:
    """Check Origin / Referer against configured ALLOWED_ORIGINS.

    Returns True if the request is from an allowed origin, or if no
    origins are configured (backward-compatible default: allow all).
    """
    origins = config.settings.allowed_origins_list
    if not origins:
        return True  # no restriction configured

    # Check Origin header first (preferred), fall back to Referer
    origin = request.headers.get("Origin", "")
    if not origin:
        referer = request.headers.get("Referer", "")
        if referer:
            origin = urlparse(referer).scheme + "://" + urlparse(referer).netloc

    if not origin:
        logger.warning(f"CSRF check: no Origin/Referer from {request.remote_addr}")
        return False

    if origin in origins:
        return True

    logger.warning(f"CSRF check: origin '{origin}' not allowed from {request.remote_addr}")
    return False


# Make a random email containing 6 characters
@bp.route('/get_random_address')
def get_random_address():
    random_string = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    domain = secrets.choice(config.settings.domain_list)
    return jsonify({"address": f"{random_string}@{domain}"}), 200

# Get an email domain
@bp.route('/get_domain')
def get_domain():
    return jsonify({"domains": config.settings.domain_list}), 200

# This route returns the contents of an inbox
@bp.route('/get_inbox')
def get_inbox():
    addr = request.args.get("address", "").lower()
    password = request.headers.get("Authorization", None)

    if re.match(config.settings.PROTECTED_ADDRESSES, addr) and password != config.settings.PASSWORD:
        return jsonify({"error": "Unauthorized"}), 401

    address_inbox = inbox_handler.read_inbox(recipient=addr)
    return jsonify(address_inbox), 200

# This route sends an email
@bp.route('/send_email', methods=['POST'])
def send_email_route():
    if not config.settings.ENABLE_SENDING:
        return jsonify({"error": "Sending is disabled"}), 403

    # CSRF check: validate Origin/Referer (H3)
    if not _origin_allowed():
        return jsonify({"error": "Forbidden"}), 403

    data = request.json

    from_address = data.get('From')
    to_address = data.get('To')
    subject = data.get('Subject')
    body = data.get('Body')

    if not all([from_address, to_address, subject, body]):
        return jsonify({"error": "Missing fields"}), 400

    if not any(from_address.endswith(domain) for domain in config.settings.domain_list):
         return jsonify({"error": f"You can only send from addresses on these domains: {', '.join(config.settings.domain_list)}"}), 403

    success, message = sender.send_email(from_address, to_address, subject, body)

    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 500