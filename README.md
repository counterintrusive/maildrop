<h1>
    <img src="pictures/icon.svg" height="32" width="auto" alt="logo" style="vertical-align: middle; margin-right: 15px;">
    Maildrop
</h1>

*A simple self-hostable disposable email inbox with SMTP server*

![App Screenshot](pictures/app.png)

## Table of Contents
- [About The Project](#about-the-project)
  - [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running with Docker](#running-with-docker)
- [Connecting to your domain](#connecting-to-your-domain)
  - [Example DNS configurations](#example-dns-configurations)
- [Configuration](#configuration)
- [Security](#security)
  - [Rate limiting](#rate-limiting)
  - [Email size limits](#email-size-limits)
  - [Per-inbox storage with eviction](#per-inbox-storage-with-eviction)
  - [Privilege separation](#privilege-separation)
  - [SMTP STARTTLS](#smtp-starttls)
  - [CSRF / Origin validation](#csrf--origin-validation)
  - [Security headers](#security-headers)
- [Sending](#sending)
- [API Reference](#api-reference)
- [License](#license)

## About The Project

Maildrop is a self-hostable disposable email service that receives emails on any address on one or more of your domains. It runs a lightweight SMTP server (port 25) and a web panel (port 5000) for browsing received emails.

It is perfect for:
- People who want to easily use multiple email addresses.
- Signing up for services without using your main email address.
- Easily creating multiple accounts on websites.

### Features

- [x] Multi-domain support (receive on multiple domains simultaneously)
- [x] Random email generation
- [x] Use custom emails
- [x] Support for password protected inboxes
- [x] Clean UI
- [x] Easy setup
- [x] Per-inbox storage with oldest-first eviction
- [x] Per-IP rate limiting
- [x] Privilege separation (drops root after binding SMTP)
- [x] (Optional) SMTP STARTTLS
- [x] (Optional) Sending emails — [Set up sending](#sending)

## Getting Started

If you wish to install maildrop and run it with Python, follow this guide. If you wish to install it with Docker instead, proceed to [Running with Docker](#running-with-docker).

### Prerequisites

- Python 3.9+
- pip
- Port 25 must be accessible (some ISPs block it — you may need a VPS)

### Installation

1.  **Clone the repository**

    ```bash
    git clone https://github.com/haileyydev/maildrop.git
    cd maildrop
    ```

2.  **Create a venv and activate it**

    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install the requirements**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure the environment**

    ```bash
    cp .env.example .env
    # Edit .env — at minimum set DOMAINS and PASSWORD
    ```

5.  **Run the application**

    ```bash
    sudo python app.py
    ```

Maildrop will be running on port 5000 (web panel) and port 25 (SMTP).

**Root is required only to bind port 25.** The SMTP server drops privileges to `nobody` immediately after binding. If you use a port redirect (e.g. `authbind`), root is not needed.

### Running with Docker

Use this command to run maildrop in a Docker container:

```bash
sudo docker run \
  -d \
  --restart unless-stopped \
  --name maildrop \
  -p 5000:5000 \
  -p 25:25 \
  -e DOMAINS="yourdomain.com" \
  -e PASSWORD="yourpassword" \
  haileyydev/maildrop:latest
```

Or with Docker Compose — add this to your `compose.yml`:

```yaml
services:
  maildrop:
    image: haileyydev/maildrop:latest
    container_name: maildrop
    restart: unless-stopped
    ports:
      - "5000:5000"
      - "25:25"
    environment:
      - DOMAINS=yourdomain.com
      - PASSWORD=yourpassword
```

Then start it: `sudo docker compose up -d`

## Connecting to your domain(s)

Follow this guide to set up receiving emails on your domain(s). Maildrop supports multiple domains — just set `DOMAINS` to a comma-separated list (e.g. `DOMAINS=domain1.com,domain2.com`).

1. **Ensure port `25` is open**  
   This is the port the SMTP server uses. Some ISPs block this — you may need a tunnel or host maildrop in the cloud.

2. **Create an `A` record for each domain**  
   Point it to the public IP address of the server running maildrop.

3. **Create an `MX` record for each domain**  
   Point it to the domain you created the `A` record on.

4. **Edit `.env` and set `DOMAINS` to your domain(s)**  
   Comma-separated list of domains to accept mail for (e.g. `DOMAINS=domain1.com,domain2.com`). If using Docker, set the `DOMAINS` environment variable directly.

---

### Example DNS configurations

**If you are running maildrop on a different domain/subdomain than the one you are receiving emails on:**

| Type | Domain                | Points To                |
| ---- | --------------------- | ------------------------ |
| `A`  | `maildrop.domain.com` | Your server's IP address |
| `MX` | `domain.com`          | `maildrop.domain.com`    |

In this configuration, access maildrop at `http://maildrop.domain.com:5000` (or preferably `https://maildrop.domain.com` behind a reverse proxy).

---

**If you are running maildrop on the same domain as the one you are receiving emails on:**

| Type | Domain       | Points To                |
| ---- | ------------ | ------------------------ |
| `A`  | `domain.com` | Your server's IP address |
| `MX` | `domain.com` | `domain.com`             |

## Configuration

Create a `.env` file (copy `.env.example` for a template). If using Docker, set these as environment variables.

| Variable                | Default            | Description                                                |
| ----------------------- | ------------------ | ---------------------------------------------------------- |
| `FLASK_HOST`            | `0.0.0.0`          | Host for the web panel.                                    |
| `FLASK_PORT`            | `5000`             | Port for the web panel.                                    |
| `SMTP_HOST`             | `0.0.0.0`          | Host for the SMTP server.                                  |
| `SMTP_PORT`             | `25`               | Port for the SMTP server.                                  |
| `DOMAINS`               | `yourdomain.com`   | Comma-separated list of domains to accept mail for. Random addresses are generated from a random domain in this list. |
| `PASSWORD`              | `password`         | Password for protected inboxes. **Change this.**           |
| `PROTECTED_ADDRESSES`   | `^admin.*`         | Regex for inboxes that require a password.                 |
| `ENABLE_SENDING`        | `false`            | Enable outbound email sending.                             |
| `SMTP_RATE_LIMIT`       | `10`               | Max SMTP connections per IP per window.                    |
| `SMTP_RATE_WINDOW`      | `60`               | Rate limit window in seconds.                              |
| `SMTP_MAX_MSGS_PER_CONN`| `20`               | Max messages per SMTP connection.                          |
| `MAX_EMAIL_SIZE`        | `10000000`         | Max raw email size in bytes (10 MB).                       |
| `MAX_EMAILS_PER_INBOX`  | `500`              | Max emails per inbox before oldest-first eviction.         |
| `DROP_PRIV_USER`        | `nobody`           | User to drop privileges to after binding SMTP port.        |
| `SMTP_TLS_CERT`         | _(empty)_          | Path to TLS certificate file for SMTP STARTTLS.            |
| `SMTP_TLS_KEY`          | _(empty)_          | Path to TLS private key file for SMTP STARTTLS.            |
| `ALLOWED_ORIGINS`       | _(empty)_          | Comma-separated origins allowed for `POST /send_email`.    |
| `FLASK_SECRET_KEY`      | _(empty)_          | Secret key for Flask session signing (auto-generated if empty). |

## Security

Maildrop includes several security features to protect your deployment.

### Rate limiting

The SMTP server enforces per-IP rate limits to prevent abuse:

- **`SMTP_RATE_LIMIT`** — max connections per IP within the window (default: 10)
- **`SMTP_RATE_WINDOW`** — sliding window in seconds (default: 60)
- **`SMTP_MAX_MSGS_PER_CONN`** — max messages accepted per connection (default: 20)

Exceeded connections receive SMTP code `452` (try again later) and are logged.

### Email size limits

Emails larger than `MAX_EMAIL_SIZE` (default 10 MB) are rejected at the SMTP protocol level and by the parser as a defence-in-depth measure.

### Per-inbox storage with eviction

Each recipient's emails are stored in a separate file under `INBOX_DIR` (default `inboxes/`). When an inbox exceeds `MAX_EMAILS_PER_INBOX` (default 500), the oldest emails are evicted first — no silent global data loss.

### Privilege separation

The SMTP server binds port 25 as root, then immediately drops privileges to `DROP_PRIV_USER` (default `nobody`). The web panel never runs as root.

### SMTP STARTTLS

Set `SMTP_TLS_CERT` and `SMTP_TLS_KEY` to enable STARTTLS on the SMTP server. When configured, the server advertises STARTTLS and upgrades connections to TLS.

### CSRF / Origin validation

When `ALLOWED_ORIGINS` is set (comma-separated), `POST /send_email` requests are validated against the `Origin` header (with `Referer` fallback). Requests from unlisted origins receive a `403 Forbidden` response.

### Security headers

The web panel sets the following HTTP security headers on all responses:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy` — strict same-origin policy
- `Referrer-Policy: strict-origin-when-cross-origin`

## Sending

Maildrop also supports sending mail as an optional feature. Visit the [Sending Guide](docs/SENDING.md) for instructions.

## API Reference

Visit the [API Reference](docs/API.md) for instructions on interacting with maildrop via the simple JSON API. The API returns the full list of configured domains via `GET /get_domain` and generates random addresses across all domains.

## License

Distributed under the GNU General Public License v3.0.
