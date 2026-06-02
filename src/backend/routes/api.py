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


# Word lists for generating human-readable local parts
# Multiple patterns avoid fingerprinting from repeated identical formats.
FIRST_NAMES = [
    "alex", "andy", "ben", "cara", "chris", "dan", "dave", "emma",
    "eric", "grace", "jade", "james", "jane", "jess", "jill", "john",
    "julia", "kate", "kurt", "lara", "luke", "maria", "mark", "matt",
    "maya", "megan", "mia", "mike", "nate", "nina", "noah", "nora",
    "owen", "paige", "paul", "quinn", "ray", "rose", "ruth", "ryan",
    "sam", "sara", "seth", "sophie", "tess", "tom", "troy", "vera",
    "vince", "wade", "will", "zara", "zoe", "adam", "amy", "anna",
    "beau", "beth", "brad", "chloe", "cole", "dana", "drew", "ella",
]

LAST_NAMES = [
    "adams", "allen", "baker", "bell", "brown", "carter", "clark",
    "cole", "cook", "cooper", "cox", "davis", "diaz", "evans", "fisher",
    "foster", "garcia", "gray", "green", "hall", "harris", "hill",
    "howard", "hughes", "james", "jenkins", "jones", "kelly", "king",
    "lee", "lewis", "long", "lopez", "martin", "miller", "moore",
    "morgan", "murphy", "nelson", "parker", "perez", "phillips", "price",
    "reed", "rivera", "roberts", "ross", "russell", "sanchez", "scott",
    "smith", "stewart", "taylor", "thomas", "turner", "walker", "ward",
    "watson", "white", "williams", "wilson", "wood", "wright", "young",
]

NOUNS = [
    "tiger", "eagle", "panda", "robin", "otter", "crane", "fox", "hawk",
    "wolf", "bear", "deer", "dove", "duck", "frog", "hare", "hawk",
    "heron", "koala", "lark", "lion", "lynx", "mole", "moose", "newt",
    "owl", "puma", "raven", "seal", "shrew", "skunk", "snail",
    "swan", "toad", "whale", "wren", "elm", "fir", "oak", "pine",
    "rose", "lily", "iris", "fern", "moss", "reed", "vine", "willow",
    "ash", "beech", "birch", "cedar", "cherry", "cypress", "hazel",
    "hemlock", "holly", "ivy", "juniper", "laurel", "maple", "myrtle",
    "olive", "pear", "plum", "poplar", "spruce", "yew", "cove", "dale",
    "dell", "edge", "ford", "gate", "glen", "hill", "knoll", "meadow",
    "moor", "peak", "ridge", "vale", "wood", "brook", "creek", "lake",
    "pond", "pool", "river", "stream", "bay", "reef", "shore", "wave",
]


def _generate_local_part() -> str:
    """Generate a human-readable local part using one of several patterns.

    Avoids high-entropy random strings that security systems flag.
    """
    num = secrets.randbelow(900) + 100  # 3-digit number
    small_num = secrets.randbelow(90) + 10  # 2-digit number
    pattern = secrets.choice([
        # first.last.number — e.g. james.smith.847
        lambda: f"{secrets.choice(FIRST_NAMES)}.{secrets.choice(LAST_NAMES)}.{num}",
        # first_last_number — e.g. emma_brown_847
        lambda: f"{secrets.choice(FIRST_NAMES)}_{secrets.choice(LAST_NAMES)}_{num}",
        # first-last-number — e.g. luke-hill-312
        lambda: f"{secrets.choice(FIRST_NAMES)}-{secrets.choice(LAST_NAMES)}-{num}",
        # first.last — e.g. alex.miller
        lambda: f"{secrets.choice(FIRST_NAMES)}.{secrets.choice(LAST_NAMES)}",
        # first_last — e.g. sam_smith
        lambda: f"{secrets.choice(FIRST_NAMES)}_{secrets.choice(LAST_NAMES)}",
        # first-last — e.g. mia-jones
        lambda: f"{secrets.choice(FIRST_NAMES)}-{secrets.choice(LAST_NAMES)}",
        # firstNUMBER — e.g. alex847
        lambda: f"{secrets.choice(FIRST_NAMES)}{num}",
        # first.noun — e.g. sam.fox
        lambda: f"{secrets.choice(FIRST_NAMES)}.{secrets.choice(NOUNS)}",
        # first_noun — e.g. kate_tiger
        lambda: f"{secrets.choice(FIRST_NAMES)}_{secrets.choice(NOUNS)}",
        # nounNUMBER — e.g. tiger312
        lambda: f"{secrets.choice(NOUNS)}{num}",
        # first.smallnum — e.g. kate.42
        lambda: f"{secrets.choice(FIRST_NAMES)}.{small_num}",
    ])
    return pattern()


# Make a random email with a human-readable local part
@bp.route('/get_random_address')
def get_random_address():
    local_part = _generate_local_part()
    domain = secrets.choice(config.settings.domain_list)
    return jsonify({"address": f"{local_part}@{domain}"}), 200

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
    # Create the inbox file if it doesn't exist yet, so the SMTP server
    # will accept mail for this address (prevents catch-all detection)
    inbox_handler.create_inbox(addr)
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