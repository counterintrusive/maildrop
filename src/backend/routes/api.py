from flask import Blueprint, render_template, request, jsonify, g, session
from .. import inbox_handler
from .. import sender
from .. import user_store
from ..auth import require_api_key, login_optional
import config
import re
import os
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


def _resolve_user() -> int | None:
    """Resolve the current user from session or API key.

    Checks session first (web login), then Authorization header (API key).
    Returns user_id or None for anonymous/guest access.
    Sets g.user_id.
    """
    # Check session first
    user_id = session.get("user_id")
    if user_id:
        g.user_id = user_id
        return user_id

    # Fall back to API key
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        raw_key = auth[len("Bearer "):].strip()
        user_id = user_store.lookup_user_by_key(raw_key)
        if user_id:
            g.user_id = user_id
            return user_id

    g.user_id = None
    return None


# Word lists for generating human-readable local parts.
# Loaded from data/ files so users can customise them without editing code.
# Multiple patterns avoid fingerprinting from repeated identical formats.
def _load_wordlist(filename: str) -> list[str]:
    path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', filename)
    try:
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.warning(f"Wordlist not found: {path}")
        return []

FIRST_NAMES = _load_wordlist('first_names.txt')
LAST_NAMES = _load_wordlist('last_names.txt')
NOUNS = _load_wordlist('nouns.txt')


def _generate_local_part() -> str:
    """Generate a human-readable local part using one of several patterns.

    Avoids high-entropy random strings that security systems flag.
    """
    num3 = secrets.randbelow(900) + 100    # 3-digit number (100-999)
    num4 = secrets.randbelow(9000) + 1000  # 4-digit number (1000-9999)
    small_num = secrets.randbelow(90) + 10  # 2-digit number (10-99)
    pattern = secrets.choice([
        # first.last.number — e.g. james.smith.847
        lambda: f"{secrets.choice(FIRST_NAMES)}.{secrets.choice(LAST_NAMES)}.{num3}",
        # first_last_number — e.g. emma_brown_847
        lambda: f"{secrets.choice(FIRST_NAMES)}_{secrets.choice(LAST_NAMES)}_{num3}",
        # first-last-number — e.g. luke-hill-312
        lambda: f"{secrets.choice(FIRST_NAMES)}-{secrets.choice(LAST_NAMES)}-{num3}",
        # first.last — e.g. alex.miller
        lambda: f"{secrets.choice(FIRST_NAMES)}.{secrets.choice(LAST_NAMES)}",
        # first_last — e.g. sam_smith
        lambda: f"{secrets.choice(FIRST_NAMES)}_{secrets.choice(LAST_NAMES)}",
        # first-last — e.g. mia-jones
        lambda: f"{secrets.choice(FIRST_NAMES)}-{secrets.choice(LAST_NAMES)}",
        # firstNUMBER — e.g. alex847
        lambda: f"{secrets.choice(FIRST_NAMES)}{num3}",
        # first.noun — e.g. sam.fox
        lambda: f"{secrets.choice(FIRST_NAMES)}.{secrets.choice(NOUNS)}",
        # first_noun — e.g. kate_tiger
        lambda: f"{secrets.choice(FIRST_NAMES)}_{secrets.choice(NOUNS)}",
        # nounNUMBER — e.g. tiger312
        lambda: f"{secrets.choice(NOUNS)}{num3}",
        # first.smallnum — e.g. kate.42
        lambda: f"{secrets.choice(FIRST_NAMES)}.{small_num}",
        # first.last.4digit — e.g. james.smith.3847
        lambda: f"{secrets.choice(FIRST_NAMES)}.{secrets.choice(LAST_NAMES)}.{num4}",
        # first_4digit — e.g. emma_3847
        lambda: f"{secrets.choice(FIRST_NAMES)}_{num4}",
        # last-4digit — e.g. smith-3847
        lambda: f"{secrets.choice(LAST_NAMES)}-{num4}",
        # initial.lastname — e.g. j.smith
        lambda: f"{secrets.choice(FIRST_NAMES)[0]}.{secrets.choice(LAST_NAMES)}",
        # initial_lastname — e.g. j_smith
        lambda: f"{secrets.choice(FIRST_NAMES)[0]}_{secrets.choice(LAST_NAMES)}",
        # initial.noun — e.g. k.tiger
        lambda: f"{secrets.choice(FIRST_NAMES)[0]}.{secrets.choice(NOUNS)}",
        # initial_noun — e.g. k_tiger
        lambda: f"{secrets.choice(FIRST_NAMES)[0]}_{secrets.choice(NOUNS)}",
    ])
    return pattern()


# Make a random email with a human-readable local part
@bp.route('/get_random_address')
def get_random_address():
    """Generate a random address.

    If the user is logged in (session or API key), the address is claimed
    for them. Otherwise it's returned unclaimed (guest mode).
    """
    user_id = _resolve_user()
    local_part = _generate_local_part()
    domain = secrets.choice(config.settings.domain_list)
    address = f"{local_part}@{domain}"

    if user_id:
        user_store.claim_address(address, user_id)

    # Create the inbox file so SMTP will accept mail
    inbox_handler.create_inbox(address)
    return jsonify({"address": address}), 200


# Get an email domain
@bp.route('/get_domain')
def get_domain():
    return jsonify({"domains": config.settings.domain_list}), 200


# This route returns the contents of an inbox
@bp.route('/get_inbox')
def get_inbox():
    """Return the inbox for a given address.

    If the user is logged in (session or API key), ownership is enforced.
    In guest mode, any address can be read (backward compatible).
    Protected addresses still require the PASSWORD header.
    """
    user_id = _resolve_user()
    addr = request.args.get("address", "").lower()
    if not addr:
        return jsonify({"error": "Missing address parameter"}), 400

    if user_id:
        # Logged-in user: enforce address ownership
        owner = user_store.address_owner(addr)
        if owner is None:
            # Address not claimed yet — allow the user to claim it
            user_store.claim_address(addr, user_id)
        elif owner != user_id:
            # Address belongs to another user — deny access
            # (unless it's a protected address with the correct password)
            password = request.headers.get("Authorization", None)
            if re.match(config.settings.PROTECTED_ADDRESSES, addr) and password == config.settings.PASSWORD:
                pass  # Allow access with correct password
            else:
                return jsonify({"error": "Unauthorized — this address belongs to another user"}), 403
    else:
        # Guest mode: check protected addresses
        password = request.headers.get("Authorization", None)
        if re.match(config.settings.PROTECTED_ADDRESSES, addr) and password != config.settings.PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

    address_inbox = inbox_handler.read_inbox(recipient=addr)
    # Create the inbox file if it doesn't exist yet, so the SMTP server
    # will accept mail for this address (prevents catch-all detection)
    inbox_handler.create_inbox(addr)
    return jsonify(address_inbox), 200


# --- API key management ---

@bp.route('/api_key', methods=['GET'])
@require_api_key
def get_api_keys():
    """Return the user's active API keys (prefixes only)."""
    keys = user_store.get_user_keys(g.user_id)
    return jsonify({"keys": keys}), 200


@bp.route('/auth/generate', methods=['POST'])
def create_api_key():
    """Create an API key for the authenticated user.

    Requires a valid session (web login).
    If the user already has an active key, it is revoked first (regenerate).
    Each user is limited to 1 active key.
    """
    user_id = _resolve_user()
    if user_id is None:
        return jsonify({"error": "You must be logged in to create an API key. Please register or log in."}), 401

    # Revoke any existing key first (regenerate)
    existing_keys = user_store.get_user_keys(user_id)
    for key in existing_keys:
        user_store.revoke_api_key(key["id"], user_id)

    try:
        new_key = user_store.generate_api_key(user_id)
        return jsonify({"api_key": new_key, "user_id": user_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/api_key/<int:key_id>', methods=['DELETE'])
@require_api_key
def revoke_api_key(key_id):
    """Revoke one of the user's API keys."""
    if user_store.revoke_api_key(key_id, g.user_id):
        return jsonify({"message": "Key revoked"}), 200
    return jsonify({"error": "Key not found"}), 404


# --- Address management ---

@bp.route('/addresses', methods=['GET'])
@require_api_key
def list_addresses():
    """Return all addresses claimed by the authenticated user."""
    addresses = user_store.user_addresses(g.user_id)
    return jsonify({"addresses": addresses}), 200


@bp.route('/addresses', methods=['POST'])
@require_api_key
def claim_address():
    """Claim a specific address for the authenticated user."""
    data = request.get_json(silent=True) or {}
    address = (data.get("address") or "").strip().lower()
    if not address or "@" not in address:
        return jsonify({"error": "Invalid address"}), 400

    # Validate domain
    domain_part = address.split("@")[1]
    if domain_part not in config.settings.domain_list:
        return jsonify({"error": f"Domain '{domain_part}' is not accepted"}), 400

    if user_store.claim_address(address, g.user_id):
        inbox_handler.create_inbox(address)
        return jsonify({"message": "Address claimed"}), 201
    return jsonify({"error": "Address already claimed"}), 409


@bp.route('/addresses/<path:address>', methods=['DELETE'])
@require_api_key
def delete_address(address):
    """Release an address claim."""
    address = address.lower()
    if user_store.delete_address(address, g.user_id):
        return jsonify({"message": "Address released"}), 200
    return jsonify({"error": "Address not found or not yours"}), 404


# This route sends an email
@bp.route('/send_email', methods=['POST'])
def send_email_route():
    if not config.settings.ENABLE_SENDING:
        return jsonify({"error": "Sending is disabled"}), 403

    # Require authentication (session or API key)
    user_id = _resolve_user()
    if user_id is None:
        return jsonify({"error": "Unauthorized — provide a valid API key or log in"}), 401

    # CSRF check: validate Origin/Referer (defence-in-depth alongside auth)
    if not _origin_allowed():
        return jsonify({"error": "Forbidden"}), 403

    data = request.json

    from_address = data.get('From')
    to_address = data.get('To')
    subject = data.get('Subject')
    body = data.get('Body')

    if not all([from_address, to_address, subject, body]):
        return jsonify({"error": "Missing fields"}), 400

    # Validate From domain with exact match (not endswith — prevents domain suffix bypass)
    from_domain = from_address.split("@")[1] if "@" in from_address else ""
    if from_domain not in config.settings.domain_list:
         return jsonify({"error": f"You can only send from addresses on these domains: {', '.join(config.settings.domain_list)}"}), 403

    success, message = sender.send_email(from_address, to_address, subject, body)

    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 500
