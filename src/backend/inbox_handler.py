import json
import os
import config
import logging

logger = logging.getLogger("maildrop")


def _inbox_path(recipient: str) -> str:
    """Return the filesystem path for a single recipient's inbox file.

    The recipient address is sanitised so it can't escape the inbox directory.
    """
    safe_name = recipient.replace("@", "_at_").replace(".", "_dot_").replace("/", "_").replace("\\", "_")
    return os.path.join(config.settings.INBOX_DIR, f"{safe_name}.json")


def _ensure_inbox_dir():
    """Create the inbox directory if it doesn't exist."""
    os.makedirs(config.settings.INBOX_DIR, exist_ok=True)


def read_inbox(recipient: str | None = None) -> dict:
    """Read inbox(es).

    If *recipient* is given, return the list of emails for that address
    (or an empty list).  If *recipient* is None, return the entire inbox
    dict keyed by address (legacy API for the web panel).
    """
    _ensure_inbox_dir()

    if recipient is not None:
        path = _inbox_path(recipient)
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    # Legacy: read all per-inbox files and merge into one dict
    inbox = {}
    try:
        for fname in os.listdir(config.settings.INBOX_DIR):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(config.settings.INBOX_DIR, fname)
            try:
                with open(path, "r") as f:
                    emails = json.load(f)
                # Reconstruct the original address from the safe filename
                addr = fname[:-5].replace("_at_", "@").replace("_dot_", ".")
                inbox[addr] = emails
            except (json.JSONDecodeError, OSError):
                continue
    except FileNotFoundError:
        pass
    return inbox


def write_inbox(data: dict):
    """Legacy: write the entire inbox dict as per-inbox files.

    Used by the web panel's /get_inbox route which still passes a full
    dict.  This splits it back into individual files.
    """
    _ensure_inbox_dir()
    for recipient, emails in data.items():
        path = _inbox_path(recipient)
        with open(path, "w") as f:
            json.dump(emails, f, indent=4)


def _evict_oldest(emails: list, max_emails: int) -> list:
    """Remove oldest emails if the list exceeds *max_emails*."""
    if len(emails) > max_emails:
        excess = len(emails) - max_emails
        logger.warning(f"Evicting {excess} oldest email(s) from inbox (cap={max_emails})")
        return emails[excess:]
    return emails


def inbox_exists(recipient: str) -> bool:
    """Check if an inbox file already exists for this recipient.

    Used by the SMTP RCPT handler to reject mail for unknown addresses,
    preventing SMTP handshake probes from detecting catch-all behaviour.
    """
    path = _inbox_path(recipient)
    return os.path.isfile(path)


def create_inbox(recipient: str):
    """Create an empty inbox file for a recipient if it doesn't exist.

    This is called when a user generates or sets an email address via the
    web panel, so the SMTP server will accept mail for it.
    """
    path = _inbox_path(recipient)
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump([], f)
        logger.info(f"Created inbox for {recipient}")


def recv_email(email_json: dict):
    """Add a new email to the recipient's per-inbox file.

    If the inbox exceeds MAX_EMAILS_PER_INBOX the oldest emails are
    evicted first (no silent data loss of the entire store).
    """
    _ensure_inbox_dir()

    recipient = email_json.get("To")
    if not recipient:
        return

    path = _inbox_path(recipient)

    # Read existing emails for this recipient only
    try:
        with open(path, "r") as f:
            emails = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        emails = []

    logger.info(f"Inbox {recipient} received email from {email_json.get('From')}")

    emails.append(email_json)

    # Evict oldest first if over cap
    emails = _evict_oldest(emails, config.settings.MAX_EMAILS_PER_INBOX)

    with open(path, "w") as f:
        json.dump(emails, f, indent=4)
