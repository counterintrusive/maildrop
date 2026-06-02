import logging
import sys
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("maildrop")

# define all possible settings
class Settings(BaseSettings):
    FLASK_HOST: str = "0.0.0.0"
    FLASK_PORT: int = Field(default=5000, ge=1, le=65535)
    SMTP_HOST: str = "0.0.0.0"
    SMTP_PORT: int = Field(default=25, ge=1, le=65535)
    INBOX_FILE_NAME: str = "inbox.json"
    MAX_INBOX_SIZE: int = Field(default=100000000, ge=1)
    PROTECTED_ADDRESSES: str = "^(admin|postmaster|abuse|webmaster|noreply|no-reply|mailer-daemon|mdaemon|root|hostmaster|usenet|news|spam|dmarc|mailnull|nobody|support|help|info|security|registrar|domain|dns|host|server|test|bounce|return-path|feedback|errors|mailer|sender|reply|list-request|list-owner|list-admin|majordomo|owner-|request-|subscribe|unsubscribe).*"
    PASSWORD: str = "password"
    DOMAINS: str = "yourdomain.com"
    ENABLE_SENDING: bool = False
    RELAY_HOST: str = ""
    RELAY_PORT: int = Field(default=2525, ge=1, le=65535)
    RELAY_USER: str = ""
    RELAY_PASS: str = ""

    # --- Rate limiting (C1) ---
    # Max connections per IP within the rate window
    SMTP_RATE_LIMIT: int = Field(default=10, ge=1)
    # Rate window in seconds
    SMTP_RATE_WINDOW: int = Field(default=60, ge=1)
    # Max messages per connection
    SMTP_MAX_MSGS_PER_CONN: int = Field(default=20, ge=1)

    # --- Email size limit (C2) ---
    # Max raw email size in bytes (default 10 MB)
    MAX_EMAIL_SIZE: int = Field(default=10_000_000, ge=1)

    # --- Per-inbox storage (C3) ---
    # Directory for per-inbox JSON files
    INBOX_DIR: str = "inboxes"
    # Max emails per inbox before oldest-first eviction
    MAX_EMAILS_PER_INBOX: int = Field(default=500, ge=1)

    # --- Privilege drop (H4) ---
    # User to drop privileges to after binding SMTP port.
    # IMPORTANT: setuid() is per-process on Linux — dropping to 'nobody' will affect
    # the Flask web server too. Only set this if the install directory is readable
    # by the target user. Leave empty to stay as root.
    DROP_PRIV_USER: str = ""

    # --- SMTP TLS (M1) ---
    # Paths to TLS cert and key for SMTP STARTTLS. Leave empty to disable.
    SMTP_TLS_CERT: str = ""
    SMTP_TLS_KEY: str = ""

    # --- CSRF protection (H3) ---
    # Comma-separated list of allowed Origin values for POST /send_email.
    # Leave empty to allow all (backward compatible).
    ALLOWED_ORIGINS: str = ""

    # --- Flask secret key (L3) ---
    # Used for signing session cookies. Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    FLASK_SECRET_KEY: str = ""

    @property
    def domain_list(self) -> list[str]:
        return [d.strip() for d in self.DOMAINS.split(",") if d.strip()]

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def DOMAIN(self) -> str:
        return self.domain_list[0] if self.domain_list else "yourdomain.com"

    model_config = SettingsConfigDict(env_file=".env")

try:
    settings = Settings()
    logger.info("Loaded configuration.")
except ValidationError as e:
    logger.critical("Configuration Error! Maildrop cannot start.")

    # print the errors in a clean way
    for error in e.errors():
        # gets the name of the field and the error message
        field_name = error['loc'][0]
        error_message = error['msg']
    
        logger.critical(f"{field_name}: {error_message}")
        
    sys.exit(1)