# AGT Voting System — Technical Specification

## 1. API Contract

### Endpoint

```
POST /api/vote
Content-Type: application/json
```

### Request Schema

```json
{
  "contestant": "<string>"
}
```

| Field        | Type   | Required | Description                      |
|-------------|--------|----------|----------------------------------|
| `contestant` | string | Yes      | Last name of contestant to vote for |

### Response Schemas

**200 OK — Vote recorded**

```json
{
  "message": "Vote recorded for <normalized_name>."
}
```

Where `<normalized_name>` is the contestant name after normalization, capitalized (e.g., `"Thompson"`).

**400 Bad Request — No client IP**

```json
{
  "detail": "Unable to determine client IP."
}
```

Returned when `request.client` is `None`.

**400 Bad Request — Invalid JSON body**

```json
{
  "detail": "Invalid request body."
}
```

Returned when the request body is not valid JSON or is not a JSON object.

**400 Bad Request — Missing contestant field**

```json
{
  "detail": "Missing required field: contestant."
}
```

Returned when the `contestant` key is absent from the JSON object.

**400 Bad Request — Invalid contestant type**

```json
{
  "detail": "Contestant must be a string."
}
```

Returned when `contestant` is present but is not a string (e.g., null, number, array, object).

**400 Bad Request — Input too long**

```json
{
  "detail": "Input exceeds maximum length of 100 characters."
}
```

Returned when the raw `contestant` string exceeds 100 characters (checked before normalization).

**400 Bad Request — Empty input**

```json
{
  "detail": "Contestant name must not be empty."
}
```

Returned when the `contestant` string, after normalization, is an empty string. Covers empty strings, whitespace-only strings, strings of only digits, and strings of only special characters.

**404 Not Found — Unknown contestant**

```json
{
  "detail": "Unknown contestant: '<normalized_name>'. Valid contestants: Chen, Jensen, Kowalski, Martinez, Nakamura, Okafor, Patel, Rodriguez, Thompson, Williams."
}
```

Returned when the normalized input does not match any contestant in the roster. The valid contestants are listed in alphabetical order.

**409 Conflict — Duplicate vote**

```json
{
  "detail": "You have already voted."
}
```

Returned when the device fingerprint already exists in the database.

**422 Unprocessable Entity — Missing User-Agent**

```json
{
  "detail": "Missing User-Agent header."
}
```

Returned when the `User-Agent` header is absent or empty in the request.

**429 Too Many Requests — Rate limit exceeded**

```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

Returned when the IP address has made more than 10 requests within the last 60 seconds.

**500 Internal Server Error — Database error**

```json
{
  "detail": "Internal server error."
}
```

Returned when an unexpected database exception occurs. Never expose tracebacks or internal details to the client. The server must run with `debug=False`.

### HTTP Status Code Summary

| Code | Meaning                  | When                                         |
|------|--------------------------|----------------------------------------------|
| 200  | OK                       | Vote successfully recorded                   |
| 400  | Bad Request              | No client IP, invalid JSON, missing field, bad type, too long, empty after normalization |
| 404  | Not Found                | Contestant not in roster                     |
| 409  | Conflict                 | Duplicate vote (fingerprint already exists)  |
| 422  | Unprocessable Entity     | Missing or empty User-Agent header           |
| 429  | Too Many Requests        | Rate limit exceeded (>10 req/min per IP)     |
| 500  | Internal Server Error    | Unexpected database error                    |

---

## 2. Data Model

### Database Lifecycle

The database connection is managed via **FastAPI's lifespan** context manager:

- **Startup**: open a `sqlite3` connection to `votes.db`, enable WAL mode and busy timeout, run `CREATE TABLE IF NOT EXISTS`, and store the connection on `app.state.db`.
- **Shutdown**: close the connection.

```python
@asynccontextmanager
async def lifespan(app):
    db = sqlite3.connect("votes.db")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute(CREATE_TABLE_SQL)
    app.state.db = db
    yield
    db.close()
```

### SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contestant TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    ip_address TEXT NOT NULL,
    user_agent TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Column Details

| Column       | Type      | Constraints              | Description                                   |
|-------------|-----------|--------------------------|-----------------------------------------------|
| `id`         | INTEGER   | PRIMARY KEY AUTOINCREMENT | Auto-incrementing unique row identifier       |
| `contestant` | TEXT      | NOT NULL                 | Normalized contestant last name (lowercase)   |
| `fingerprint`| TEXT      | NOT NULL, UNIQUE         | SHA-256 hash of IP + `"|"` + User-Agent       |
| `ip_address` | TEXT      | NOT NULL                 | Client IP from `request.client.host`          |
| `user_agent` | TEXT      | NOT NULL                 | Raw User-Agent header value                   |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Time the vote was recorded                    |

The database file is stored at `votes.db` in the backend working directory.

All queries MUST use parameterized statements. No string interpolation or concatenation in SQL.

---

## 3. Contestant Roster

Hardcoded set of exactly 10 last names. Stored as a Python `set` of lowercase strings for O(1) lookup:

```python
CONTESTANTS = {
    "thompson",
    "rodriguez",
    "nakamura",
    "chen",
    "williams",
    "kowalski",
    "martinez",
    "okafor",
    "patel",
    "jensen",
}
```

Validation: after normalization, check `normalized_name in CONTESTANTS`.

For display purposes (error messages, frontend list), sort alphabetically and capitalize:

```
Chen, Jensen, Kowalski, Martinez, Nakamura, Okafor, Patel, Rodriguez, Thompson, Williams
```

---

## 4. Name Normalization

Three steps applied in order:

1. **Trim whitespace** — strip leading and trailing whitespace characters.
2. **Lowercase** — convert all characters to lowercase.
3. **Strip non-alpha** — remove all characters that are NOT `a-z` using regex `[^a-z]`.

### Worked Examples

| Raw Input              | After Trim           | After Lowercase      | After Strip (final)  | Result    |
|-----------------------|----------------------|----------------------|----------------------|-----------|
| `"Thompson"`           | `"Thompson"`          | `"thompson"`          | `"thompson"`          | Valid     |
| `"  Rodriguez  "`      | `"Rodriguez"`         | `"rodriguez"`         | `"rodriguez"`         | Valid     |
| `"  O'Kafor  "`        | `"O'Kafor"`           | `"o'kafor"`           | `"okafor"`            | Valid     |
| `"CHEN"`               | `"CHEN"`              | `"chen"`              | `"chen"`              | Valid     |
| `"  na-ka-mu-ra  "`    | `"na-ka-mu-ra"`       | `"na-ka-mu-ra"`       | `"nakamura"`          | Valid     |
| `"Martínez"`           | `"Martínez"`          | `"martínez"`          | `"martnez"`           | Not Found |
| `"Willi@ms!"`          | `"Willi@ms!"`         | `"willi@ms!"`         | `"willims"`           | Not Found |
| `"   "`                | `""`                  | `""`                  | `""`                  | Empty     |
| `"123"`                | `"123"`               | `"123"`               | `""`                  | Empty     |
| `"!!!"`                | `"!!!"`               | `"!!!"`               | `""`                  | Empty     |
| `"<script>alert(1)</script>"` | `"<script>alert(1)</script>"` | `"<script>alert(1)</script>"` | `"scriptalertscript"` | Not Found |
| `"'; DROP TABLE votes;--"` | `"'; DROP TABLE votes;--"` | `"'; DROP TABLE votes;--"` | `"droptablevotes"` | Not Found |

---

## 5. Vote Integrity

### Device Fingerprint

```
fingerprint = SHA-256(ip_address + "|" + user_agent)
```

- **IP address**: obtained from `request.client.host`, normalized (see below). Never use `X-Forwarded-For` or any proxy header.
- **User-Agent**: raw value from the `User-Agent` HTTP header.
- **Separator**: a literal pipe character `"|"` between IP and User-Agent to prevent collisions (e.g., IP `"1.2.3.4"` + UA `"5Mozilla"` vs IP `"1.2.3.45"` + UA `"Mozilla"` would collide without a delimiter).
- **Hash**: SHA-256 of the delimited concatenation, output as lowercase hex string.

Example:
```
IP: "127.0.0.1"
User-Agent: "Mozilla/5.0"
Input: "127.0.0.1|Mozilla/5.0"
Fingerprint: SHA-256("127.0.0.1|Mozilla/5.0") → "a1b2c3..."
```

### IP Normalization

Before using the IP address for fingerprinting or rate limiting, normalize it using Python's `ipaddress` module to prevent IPv4-mapped IPv6 addresses from creating different fingerprints than their IPv4 equivalents:

```python
import ipaddress

def normalize_ip(raw_ip: str) -> str:
    addr = ipaddress.ip_address(raw_ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    return str(addr)
```

Example: `"::ffff:127.0.0.1"` normalizes to `"127.0.0.1"`.

The normalized IP is used for both the fingerprint hash and rate-limit key. The raw `request.client.host` value is stored in the `ip_address` column for debugging.

### Enforcement

- The `fingerprint` column has a `UNIQUE` constraint in SQLite.
- Before inserting, attempt the INSERT. If `IntegrityError` is raised (duplicate fingerprint), return 409.
- One vote TOTAL per fingerprint — not per contestant. A voter cannot vote for multiple contestants.

---

## 6. Rate Limiting

### Mechanism

- In-memory Python dictionary: `dict[str, list[float]]` mapping normalized IP address to a list of request timestamps.
- Protected by an `asyncio.Lock` to ensure safety under concurrent async access.
- On each request, before any other processing:
  1. Acquire the lock.
  2. Get the current time.
  3. Retrieve the list of timestamps for this IP.
  4. Filter out timestamps older than 60 seconds.
  5. If the filtered list has 10 or more entries, release the lock and return 429.
  6. Otherwise, append the current timestamp.
  7. **Periodic sweep**: every 50 requests (tracked by a global counter), iterate the dictionary and remove entries where all timestamps are older than 60 seconds. This prevents unbounded memory growth from stale IPs.
  8. Release the lock and proceed.

### Parameters

| Parameter       | Value |
|----------------|-------|
| Window          | 60 seconds |
| Max requests    | 10 per IP per window |
| Storage         | In-memory dictionary (resets on server restart) |
| Sweep interval  | Every 50 requests |
| Concurrency     | `asyncio.Lock` protects all dict access |

### Deployment Constraint

The in-memory rate limiter is **not shared across OS processes**. The application MUST be run with `--workers 1` (single Uvicorn worker). This constraint should be documented in the project README.

### Scope

Rate limiting applies to the `/api/vote` endpoint only. It counts all requests regardless of whether the vote is valid. The rate-limit key is the **normalized** IP address (see IP Normalization).

---

## 7. Processing Order

Requests to `POST /api/vote` are processed in this exact order:

```
 1. Check request.client      → 400 if None (no client IP available)
 2. Rate limit check          → 429 if exceeded
 3. Parse JSON body manually  → 400 if invalid JSON or not an object
 4. Check 'contestant' field  → 400 if missing
 5. Check type is string      → 400 if not a string
 6. Max length check (100)    → 400 if > 100 characters
 7. Normalize name            → (trim, lowercase, strip non-alpha)
 8. Empty check               → 400 if empty after normalization
 9. Roster check              → 404 if not in contestant set
10. Check User-Agent header   → 422 if missing or empty
11. Normalize IP address      → (see IP Normalization below)
12. Compute fingerprint       → SHA-256(normalized_ip + "|" + user_agent)
13. Insert vote into DB       → 409 if duplicate fingerprint
14. Return success            → 200
```

This order ensures that cheap checks run first and expensive operations (DB writes) run last.

**Step 1 — request.client**: If `request.client` is `None` (which can happen in certain ASGI configurations), return 400 with `{"detail": "Unable to determine client IP."}`.

**Step 3 — Manual JSON parsing**: Do NOT rely on FastAPI/Pydantic auto-validation for the request body. Instead, parse the body manually using `await request.json()` inside a `try/except` block. This gives full control over error messages and status codes (FastAPI's auto-validation returns 422 with a different error format than specified). A Pydantic `VoteRequest` model MAY be kept in the code as documentation, but must not be used as a route parameter type.

---

## 8. Input Sanitization

### Max Length

- The raw `contestant` string is checked for length **before** normalization.
- Maximum: 100 characters.
- Strings exceeding 100 characters are rejected with 400.

### SQL Injection Prevention

- All database queries use parameterized statements with `?` placeholders.
- No string interpolation or f-strings in SQL queries.
- Example: `cursor.execute("INSERT INTO votes (contestant, fingerprint, ip_address, user_agent) VALUES (?, ?, ?, ?)", (contestant, fingerprint, ip, ua))`

### XSS Prevention

- The normalization regex `[^a-z]` strips all non-lowercase-alpha characters.
- After normalization, only characters `a-z` survive — no HTML, no JavaScript, no special characters.
- Raw input is never stored; only the normalized name is written to the database.

### Other

- Non-string types for `contestant` are rejected before any processing.
- `null` / `None` values are rejected as invalid type.

---

## 9. Logging

Use Python's built-in `logging` module. Configure a logger named `"agt"` at `INFO` level.

### What to Log

| Level     | Event                                      | Example message                              |
|-----------|--------------------------------------------|----------------------------------------------|
| `INFO`    | Vote successfully recorded                 | `"Vote recorded: contestant=thompson"`        |
| `WARNING` | Duplicate vote rejected                    | `"Duplicate vote rejected"`                   |
| `WARNING` | Rate limit exceeded                        | `"Rate limit exceeded for IP"`                |
| `WARNING` | Validation error (any 400/404/422)         | `"Validation error: Missing required field: contestant."` |
| `ERROR`   | Database exception                         | `"Database error: <exception message>"`       |

### What NOT to Log

- Do **not** log raw IP addresses (use `"IP"` as placeholder in messages).
- Do **not** log User-Agent strings.
- Do **not** log request bodies.

---

## 10. Frontend Specification

### Page Setup

- Single page: `app/page.tsx` (or `app/page.jsx`)
- Directive: `"use client"` at top of file
- Styling: Tailwind CSS for layout, MUI components for form elements

### Components

| Component    | MUI Type     | Props / Config                                   |
|-------------|-------------|--------------------------------------------------|
| Text input   | `TextField`  | `label="Contestant Last Name"`, `fullWidth`       |
| Submit button| `Button`     | `variant="contained"`, text: `"Vote"`             |
| Feedback     | `Alert`      | `severity` bound to state (`success` or `error`)  |

### State Variables

```typescript
const [contestant, setContestant] = useState("")
const [loading, setLoading] = useState(false)
const [message, setMessage] = useState("")
const [severity, setSeverity] = useState<"success" | "error">("success")
const [voted, setVoted] = useState(false)
```

### Behavior

1. User types a contestant last name into the TextField.
2. User clicks "Vote" button.
3. Button shows loading state (`loading = true`). Form is disabled during request.
4. Frontend sends `POST` to `${NEXT_PUBLIC_API_URL}/api/vote` with `{ "contestant": value }`.
5. On success (200): set `message` from response, `severity = "success"`, `voted = true`.
6. On error (4xx/5xx): set `message` from `detail` field, `severity = "error"`.
7. On network failure (fetch throws): set `message = "Network error. Please try again."`, `severity = "error"`.
8. After successful vote (`voted = true`): TextField and Button are disabled permanently for the session.
9. The Alert is only displayed when `message` is non-empty.

### Contestant List Display

Display the list of valid contestants on the page so voters know who they can vote for. Show as a simple text list:

```
Valid contestants: Chen, Jensen, Kowalski, Martinez, Nakamura, Okafor, Patel, Rodriguez, Thompson, Williams
```

### API URL Configuration

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
```

### CORS

The FastAPI backend must allow CORS requests from the frontend origin. Configure via `CORSMiddleware` with:
- `allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]`
- `allow_methods=["POST"]`
- `allow_headers=["Content-Type"]`

---

## 11. Edge Cases

| # | Input / Scenario                     | Expected Behavior                              | HTTP Status |
|---|--------------------------------------|------------------------------------------------|-------------|
| 1 | `""` (empty string)                  | Normalize → empty → "Contestant name must not be empty." | 400 |
| 2 | `"   "` (whitespace only)            | Trim → empty → normalize → empty → "Contestant name must not be empty." | 400 |
| 3 | `"!@#$%^&*()"` (special chars only) | Normalize → empty → "Contestant name must not be empty." | 400 |
| 4 | `"12345"` (digits only)              | Normalize → empty → "Contestant name must not be empty." | 400 |
| 5 | `"THOMPSON"` (all uppercase)         | Normalize → "thompson" → match → vote recorded | 200 |
| 6 | `"  Thompson  "` (leading/trailing)  | Trim → "Thompson" → normalize → "thompson" → match → vote recorded | 200 |
| 7 | `"O'Kafor"` (special chars in name) | Normalize → "okafor" → match → vote recorded  | 200 |
| 8 | `"Yamamoto"` (unknown contestant)    | Normalize → "yamamoto" → not in roster → "Unknown contestant" | 404 |
| 9 | `"'; DROP TABLE votes;--"` (SQL injection) | Normalize → "droptablevotes" → not in roster → "Unknown contestant" (parameterized queries prevent injection regardless) | 404 |
| 10 | `"<script>alert('xss')</script>"` (XSS) | Normalize → "scriptalertxssscript" → not in roster → "Unknown contestant" | 404 |
| 11 | `"a" * 101` (over 100 chars)         | Length check fails → "Input exceeds maximum length of 100 characters." | 400 |
| 12 | Same fingerprint votes again         | UNIQUE constraint → "You have already voted." | 409 |
| 13 | `{"name": "Thompson"}` (missing field) | Missing `contestant` key → "Missing required field: contestant." | 400 |
| 14 | `{"contestant": null}` (null value)  | Not a string → "Contestant must be a string." | 400 |
| 15 | `{"contestant": 42}` (non-string)    | Not a string → "Contestant must be a string." | 400 |
| 16 | Request without User-Agent header     | Missing header → "Missing User-Agent header." | 422 |
| 17 | 11th request in 60 seconds from same IP | Rate limit → "Rate limit exceeded. Try again later." | 429 |

---

## Non-Features (Explicitly Excluded)

The following are **not** part of this system and must not be built:

- No admin panel or admin endpoints
- No vote results or tally endpoint
- No leaderboard or dashboard
- No WebSocket or real-time updates
- No analytics or logging endpoint
- No user accounts or authentication
- No contestant management (roster is hardcoded)
- No pagination, filtering, or search
- No file uploads
- No email or notification system
