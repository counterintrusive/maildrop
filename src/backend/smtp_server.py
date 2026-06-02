import asyncore
import time
import logging
import os
import pwd
import ssl
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import MISSING
from . import email_parser, inbox_handler
import config

# Disable aiosmtpd's logging
logging.getLogger('mail.log').setLevel(logging.ERROR)

logger = logging.getLogger("maildrop")


class RateLimiter:
    """Simple sliding-window per-IP rate limiter."""

    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self._clients: dict[str, list[float]] = {}

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        timestamps = self._clients.get(ip, [])
        # Prune entries outside the window
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= self.limit:
            self._clients[ip] = timestamps
            return False
        timestamps.append(now)
        self._clients[ip] = timestamps
        return True

    def cleanup(self):
        """Remove stale entries to prevent memory growth."""
        now = time.monotonic()
        cutoff = now - self.window
        stale = [ip for ip, ts in self._clients.items() if all(t <= cutoff for t in ts)]
        for ip in stale:
            del self._clients[ip]


# Global rate limiter instance
_rate_limiter = RateLimiter(
    limit=config.settings.SMTP_RATE_LIMIT,
    window=config.settings.SMTP_RATE_WINDOW,
)


# Class for SMTP server logic
class SMTPServer:
    def __init__(self):
        self._msg_count: dict[str, int] = {}

    # This function is called when the server receives an email
    async def handle_DATA(self, server, session, envelope):
        client_ip = session.peer[0]

        # --- Rate limiting (C1) ---
        if not _rate_limiter.allow(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return '452 Too many connections from your IP — try again later'

        # --- Per-connection message cap ---
        self._msg_count.setdefault(client_ip, 0)
        self._msg_count[client_ip] += 1
        if self._msg_count[client_ip] > config.settings.SMTP_MAX_MSGS_PER_CONN:
            logger.warning(f"Message limit per connection exceeded for {client_ip}")
            return '452 Message limit per connection reached'

        # --- Email size check (C2) ---
        if len(envelope.content) > config.settings.MAX_EMAIL_SIZE:
            logger.warning(f"Email too large ({len(envelope.content)} bytes) from {client_ip}")
            return '552 Message size exceeds fixed limit'

        try:
            parsed_email = email_parser.email_bytes_to_json(envelope.content)
            if not any(parsed_email['To'].endswith(domain) for domain in config.settings.domain_list):
                return '500 Could not process email'

            inbox_handler.recv_email(parsed_email)
        except Exception as e:
            logger.error(f"Failed to process email from {client_ip}: {e}")
            return '500 Could not process email'

        logger.info(f"Accepted email from {client_ip} | from={parsed_email.get('From')} to={parsed_email.get('To')}")
        return '250 Message accepted for delivery'

    async def handle_EHLO(self, server, session, envelope, hostname=None, responses=None):
        client_ip = session.peer[0]
        logger.info(f"SMTP EHLO from {client_ip}")
        if responses is not None:
            # New-style hook: framework does NOT set session.host_name —
            # the hook must do it, otherwise MAIL FROM returns 503.
            session.host_name = hostname
            return responses
        # Fallback for old-style callers
        return ['250-Hello', '250 HELP']

    async def handle_HELO(self, server, session, envelope):
        client_ip = session.peer[0]
        logger.info(f"SMTP HELO from {client_ip}")
        return '250 Hello'

    async def handle_QUIT(self, server, session, envelope):
        client_ip = session.peer[0]
        logger.info(f"SMTP QUIT from {client_ip}")
        return '221 Bye'

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        client_ip = session.peer[0]
        logger.info(f"SMTP RCPT from {client_ip} -> {address}")
        # Return MISSING to let the framework add the recipient to envelope.rcpt_tos
        return MISSING


def _drop_privileges(user: str):
    """Drop root privileges to the given unprivileged user (H4).

    No-op if user is empty (stay as root).
    IMPORTANT: setuid() is per-process on Linux — this affects ALL threads.
    The Flask web server will also run as this user, so the install directory
    must be readable by the target user.
    """
    if not user:
        return
    try:
        pw_entry = pwd.getpwnam(user)
    except KeyError:
        logger.warning(f"User '{user}' not found; keeping root privileges")
        return

    uid = pw_entry.pw_uid
    gid = pw_entry.pw_gid

    # Set group and supplementary groups first (requires root)
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)

    logger.info(f"Dropped privileges to user '{user}' (uid={uid}, gid={gid})")


# This function sets up and runs the SMTP server
def run_smtp_server(host: str = "0.0.0.0", port: int = 25):
    logger.info(f"Starting SMTP server on {host}:{port}")

    handler = SMTPServer()

    # Build TLS context if cert/key paths are configured (M1)
    tls_context = None
    if config.settings.SMTP_TLS_CERT and config.settings.SMTP_TLS_KEY:
        try:
            tls_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            tls_context.load_cert_chain(
                config.settings.SMTP_TLS_CERT,
                config.settings.SMTP_TLS_KEY,
            )
            logger.info("SMTP STARTTLS enabled")
        except Exception as e:
            logger.warning(f"Failed to load TLS cert/key, STARTTLS disabled: {e}")

    controller = Controller(
        handler,
        hostname=host,
        port=port,
        server_hostname=config.settings.DOMAIN,
        data_size_limit=config.settings.MAX_EMAIL_SIZE,
        tls_context=tls_context,
    )

    try:
        controller.start()
    except Exception as e:
        logger.critical(f"Failed to start SMTP server: {e}")
        return

    # Drop privileges after binding the port (H4)
    _drop_privileges(config.settings.DROP_PRIV_USER)

    asyncore.loop()
