# Maildrop+ API

## Authentication

Maildrop+ supports two authentication methods:

1. **Session-based** — used by the web UI. Login via `POST /auth/login`, then session cookie is set automatically.
2. **API key** — for programmatic/agent access. Pass as `Authorization: Bearer <key>` header.

API keys are generated on registration and can be retrieved via `GET /auth/me` or regenerated via `POST /auth/generate`.

---

## Auth Endpoints

### Register

```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response** `201`
```json
{
  "message": "Registered successfully",
  "api_key": "md_abc123...",
  "user": {"id": 1, "email": "user@example.com"}
}
```

Rate limited: 10 attempts per 60 seconds per IP.

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response** `200`
```json
{
  "message": "Logged in",
  "user": {"id": 1, "email": "user@example.com"},
  "has_api_key": true
}
```

Rate limited: 10 attempts per 60 seconds per IP.

### Logout

```http
POST /auth/logout
```

**Response** `200`
```json
{
  "message": "Logged out"
}
```

### Get Current User

```http
GET /auth/me
```

Requires session (cookie). Returns user info, flags, and API key.

**Response** `200`
```json
{
  "authenticated": true,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "flags": "custom_email",
    "created_at": "2025-12-01 12:00:00",
    "label": ""
  },
  "has_api_key": true,
  "api_key": "md_abc123...",
  "keys": [
    {
      "id": 1,
      "key_prefix": "md_abc1234",
      "raw_key": "md_abc123...",
      "created_at": "2025-12-01 12:00:00"
    }
  ],
  "flags": ["custom_email"]
}
```

### Login Page (HTML)

```http
GET /auth/login
```

Renders the login page. Redirects to `/` if already logged in.

### Register Page (HTML)

```http
GET /auth/register
```

Renders the registration page. Redirects to `/` if already logged in.

---

## API Key Management

### List API Keys

```http
GET /api_key
Authorization: Bearer <key>
```

**Response** `200`
```json
{
  "keys": [
    {
      "id": 1,
      "key_prefix": "md_abc1234",
      "raw_key": "md_abc123...",
      "created_at": "2025-12-01 12:00:00"
    }
  ]
}
```

### Generate / Regenerate API Key

```http
POST /auth/generate
Authorization: Bearer <key>
```

Revokes any existing key and generates a new one. Each user is limited to 1 active key.

**Response** `201`
```json
{
  "api_key": "md_newkey...",
  "user_id": 1
}
```

Rate limited: 30 requests per 60 seconds per IP.

### Revoke API Key

```http
DELETE /api_key/<key_id>
Authorization: Bearer <key>
```

**Response** `200`
```json
{
  "message": "Key revoked"
}
```

---

## Address Management

### Generate Random Address

```http
GET /address
```

Generates a random human-readable address (e.g. `james.smith.847@yourdomain.com`). If the user is authenticated (session or API key), the address is automatically claimed. Guests get an unclaimed address.

**Response** `200`
```json
{
  "address": "james.smith.847@yourdomain.com"
}
```

### List Owned Addresses

```http
GET /addresses
Authorization: Bearer <key>
```

Returns all addresses claimed by the authenticated user.

**Response** `200`
```json
{
  "addresses": [
    "james.smith.847@yourdomain.com",
    "alex.miller@yourdomain.com"
  ]
}
```

### Claim a Specific Address

```http
POST /addresses
Content-Type: application/json
Authorization: Bearer <key>

{
  "address": "custom@yourdomain.com"
}
```

Claims a specific address for the authenticated user. Requires the `custom_email` flag on the user account. Max 10 addresses per user.

**Response** `201`
```json
{
  "message": "Address claimed"
}
```

Rate limited: 30 requests per 60 seconds per IP.

### Delete (Release) an Address

```http
DELETE /addresses/<address>
Authorization: Bearer <key>
```

Releases an address claim and removes its inbox file from disk.

**Response** `200`
```json
{
  "message": "Address released"
}
```

---

## Inbox

### Get Inbox

```http
GET /inbox?address=you@yourdomain.com
```

Returns the inbox for a given address. If the user is authenticated, ownership is enforced (you can only read addresses you own). Guests can read any unclaimed address. Protected addresses require the `Authorization` header with the configured password.

**Parameters**
| Parameter | Description               |
| --------- | ------------------------- |
| `address` | The email address to get. |

**Response** `200`
```json
[
  {
    "From": "sender@example.com",
    "To": "you@yourdomain.com",
    "Subject": "Hello",
    "Timestamp": 1764072990,
    "Body": "This is a test email.",
    "Sent": "Nov 25 at 12:16:30",
    "ContentType": "Text"
  }
]
```

---

## Send Email

### Send an Email

```http
POST /send
Content-Type: application/json
Authorization: Bearer <key>

{
  "From": "you@yourdomain.com",
  "To": "friend@yourdomain.com",
  "Subject": "Hello",
  "Body": "This is a test email."
}
```

Sends an email between addresses on accepted domains. Both `From` and `To` must be on a configured domain (prevents open relay). Authenticated users can only send from addresses they own.

Requires `ENABLE_SENDING = True` in config.

**Response** `200`
```json
{
  "message": "Email sent"
}
```

---

## Domains

### Get Domains

```http
GET /domains
```

Returns the list of accepted email domains.

**Response** `200`
```json
{
  "domains": ["yourdomain.com"]
}
```

---

## Error Responses

All endpoints return errors in a consistent format:

```json
{
  "error": "Description of what went wrong"
}
```

Common HTTP status codes:
| Code | Meaning                                  |
| ---- | ---------------------------------------- |
| 200  | Success                                  |
| 201  | Created                                  |
| 400  | Bad request (missing/invalid parameters) |
| 401  | Unauthorized (not logged in or bad key)  |
| 403  | Forbidden (not your resource)            |
| 404  | Not found                                |
| 409  | Conflict (e.g. email already registered) |
| 429  | Rate limited                             |
| 500  | Server error                             |

---

## Rate Limiting

| Endpoint(s)                          | Limit              |
| ------------------------------------ | ------------------ |
| `POST /auth/login`                   | 10 per 60s per IP  |
| `POST /auth/register`                | 10 per 60s per IP  |
| `POST /addresses`                    | 30 per 60s per IP  |
| `POST /auth/generate`                | 30 per 60s per IP  |
| SMTP server (per connection)         | 100 messages       |
