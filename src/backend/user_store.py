import sqlite3
import os
import secrets
import hashlib
import logging
import config

logger = logging.getLogger("maildrop")

DB_PATH = os.path.join(config.settings.INBOX_DIR, "..", "maildrop.db")


def _get_db() -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    db_path = DB_PATH
    db_dir = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist, migrate if they do."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL DEFAULT '',
            flags           TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            label           TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key_hash    TEXT NOT NULL UNIQUE,
            key_prefix  TEXT NOT NULL,
            raw_key     TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            revoked     INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS addresses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            address     TEXT NOT NULL UNIQUE,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
        CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
        CREATE INDEX IF NOT EXISTS idx_addresses_address ON addresses(address);
        CREATE INDEX IF NOT EXISTS idx_addresses_user_id ON addresses(user_id);
    """)

    # Migration: add missing columns for databases created before the schema update
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "email" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
        # Assign placeholder emails to existing rows that have empty email
        rows = conn.execute("SELECT id FROM users WHERE email = ''").fetchall()
        for row in rows:
            placeholder = f"user_{row['id']}@migrated.local"
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (placeholder, row['id']))
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        logger.info("Migrated users table: added email column")
    if "password_hash" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
        logger.info("Migrated users table: added password_hash column")

    # Migration: add flags column
    if "flags" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN flags TEXT NOT NULL DEFAULT ''")
        logger.info("Migrated users table: added flags column")

    # Migration: add raw_key column to api_keys
    api_cols = {row[1] for row in conn.execute("PRAGMA table_info(api_keys)").fetchall()}
    if "raw_key" not in api_cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN raw_key TEXT NOT NULL DEFAULT ''")
        logger.info("Migrated api_keys table: added raw_key column")

    conn.commit()
    conn.close()
    logger.info("Database initialised")


def _hash_key(key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a random salt."""
    salt = secrets.token_hex(16)
    return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"


def _check_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash."""
    if "$" not in stored:
        return False
    salt, expected = stored.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == expected


def create_user(email: str, password: str, label: str = "") -> int:
    """Create a new user with email and password. Returns their ID."""
    password_hash = _hash_password(password)
    conn = _get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, label) VALUES (?, ?, ?)",
            (email, password_hash, label),
        )
        user_id = cur.lastrowid
        conn.commit()
        logger.info(f"Created user {user_id} ({email})")
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Email '{email}' is already registered")
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> int | None:
    """Return user_id if credentials are valid, else None."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    if _check_password(password, row["password_hash"]):
        return row["id"]
    return None


def get_user_by_id(user_id: int) -> dict | None:
    """Return user info dict or None."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, email, flags, created_at, label FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_user_by_email(email: str) -> dict | None:
    """Return user info dict or None."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, email, created_at, label FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def generate_api_key(user_id: int) -> str:
    """Generate a new API key for a user. Returns the raw key (show once).

    Enforces a limit of 1 active (non-revoked) key per user.
    """
    conn = _get_db()
    # Check existing active keys
    active = conn.execute(
        "SELECT COUNT(*) AS cnt FROM api_keys WHERE user_id = ? AND revoked = 0",
        (user_id,),
    ).fetchone()["cnt"]
    if active >= 1:
        conn.close()
        raise ValueError("User already has an active API key (max 1)")

    raw = "md_" + secrets.token_hex(32)
    prefix = raw[:10]
    key_hash = _hash_key(raw)
    conn.execute(
        "INSERT INTO api_keys (user_id, key_hash, key_prefix, raw_key) VALUES (?, ?, ?, ?)",
        (user_id, key_hash, prefix, raw),
    )
    conn.commit()
    conn.close()
    logger.info(f"Generated API key for user {user_id} (prefix={prefix})")
    return raw


def lookup_user_by_key(raw_key: str) -> int | None:
    """Return user_id if the API key is valid and not revoked, else None."""
    key_hash = _hash_key(raw_key)
    conn = _get_db()
    row = conn.execute(
        "SELECT user_id FROM api_keys WHERE key_hash = ? AND revoked = 0",
        (key_hash,),
    ).fetchone()
    conn.close()
    return row["user_id"] if row else None


def get_user_keys(user_id: int) -> list[dict]:
    """Return active API keys for a user (includes raw_key for display)."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, key_prefix, raw_key, created_at FROM api_keys WHERE user_id = ? AND revoked = 0 ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def revoke_api_key(key_id: int, user_id: int) -> bool:
    """Revoke an API key. Returns True if found and revoked."""
    conn = _get_db()
    cur = conn.execute(
        "UPDATE api_keys SET revoked = 1 WHERE id = ? AND user_id = ? AND revoked = 0",
        (key_id, user_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def claim_address(address: str, user_id: int) -> bool:
    """Claim an address for a user. Returns True if claimed, False if taken.

    Enforces a maximum of 10 addresses per user.
    """
    conn = _get_db()
    try:
        # Check address limit
        count = conn.execute(
            "SELECT COUNT(*) FROM addresses WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if count >= 10:
            conn.close()
            raise ValueError("Address limit reached (max 10 addresses per user)")

        conn.execute(
            "INSERT INTO addresses (user_id, address) VALUES (?, ?)",
            (user_id, address),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def address_owner(address: str) -> int | None:
    """Return the user_id that owns an address, or None."""
    conn = _get_db()
    row = conn.execute(
        "SELECT user_id FROM addresses WHERE address = ?",
        (address,),
    ).fetchone()
    conn.close()
    return row["user_id"] if row else None


def user_addresses(user_id: int) -> list[str]:
    """Return all addresses claimed by a user."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT address FROM addresses WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [r["address"] for r in rows]


def user_has_flag(user_id: int, flag: str) -> bool:
    """Check if a user has a specific flag set.

    Flags are stored as a comma-separated list in the `flags` column.
    """
    user = get_user_by_id(user_id)
    if user is None:
        return False
    user_flags = [f.strip() for f in user.get("flags", "").split(",") if f.strip()]
    return flag in user_flags


def set_user_flag(user_id: int, flag: str) -> None:
    """Add a flag to a user (idempotent)."""
    conn = _get_db()
    user = get_user_by_id(user_id)
    if user is None:
        conn.close()
        return
    current_flags = [f.strip() for f in user.get("flags", "").split(",") if f.strip()]
    if flag not in current_flags:
        current_flags.append(flag)
        new_flags = ",".join(current_flags)
        conn.execute("UPDATE users SET flags = ? WHERE id = ?", (new_flags, user_id))
        conn.commit()
    conn.close()


def delete_address(address: str, user_id: int) -> bool:
    """Delete an address claim. Returns True if deleted."""
    conn = _get_db()
    cur = conn.execute(
        "DELETE FROM addresses WHERE address = ? AND user_id = ?",
        (address, user_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0
