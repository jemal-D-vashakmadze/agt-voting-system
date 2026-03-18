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

### HTTP Status Code Summary

| Code | Meaning                  | When                                         |
|------|--------------------------|----------------------------------------------|
| 200  | OK                       | Vote successfully recorded                   |
| 400  | Bad Request              | Invalid JSON, missing field, bad type, too long, empty after normalization |
| 404  | Not Found                | Contestant not in roster                     |
| 409  | Conflict                 | Duplicate vote (fingerprint already exists)  |
| 422  | Unprocessable Entity     | Missing or empty User-Agent header           |
| 429  | Too Many Requests        | Rate limit exceeded (>10 req/min per IP)     |

---

## 2. Data Model

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
| `fingerprint`| TEXT      | NOT NULL, UNIQUE         | SHA-256 hash of IP + User-Agent               |
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
| `"Martínez"`           | `"Martínez"`          | `"martínez"`          | `"martnez"`           | Valid     |
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
fingerprint = SHA-256(ip_address + user_agent)
```

- **IP address**: obtained from `request.client.host`. Never use `X-Forwarded-For` or any proxy header.
- **User-Agent**: raw value from the `User-Agent` HTTP header.
- **Hash**: SHA-256 of the concatenation (no separator), output as lowercase hex string.

Example:
```
IP: "127.0.0.1"
User-Agent: "Mozilla/5.0"
Input: "127.0.0.1Mozilla/5.0"
Fingerprint: SHA-256("127.0.0.1Mozilla/5.0") → "a1b2c3..."
```

### Enforcement

- The `fingerprint` column has a `UNIQUE` constraint in SQLite.
- Before inserting, attempt the INSERT. If `IntegrityError` is raised (duplicate fingerprint), return 409.
- One vote TOTAL per fingerprint — not per contestant. A voter cannot vote for multiple contestants.

---

## 6. Rate Limiting

### Mechanism

- In-memory Python dictionary: `dict[str, list[float]]` mapping IP address to a list of request timestamps.
- On each request, before any other processing:
  1. Get the current time.
  2. Retrieve the list of timestamps for this IP.
  3. Filter out timestamps older than 60 seconds.
  4. If the filtered list has 10 or more entries, return 429.
  5. Otherwise, append the current timestamp and proceed.

### Parameters

| Parameter     | Value |
|--------------|-------|
| Window        | 60 seconds |
| Max requests  | 10 per IP per window |
| Storage       | In-memory dictionary (resets on server restart) |

### Scope

Rate limiting applies to the `/api/vote` endpoint only. It counts all requests regardless of whether the vote is valid.

---

## 7. Processing Order

Requests to `POST /api/vote` are processed in this exact order:

```
1. Rate limit check         → 429 if exceeded
2. Parse JSON body          → 400 if invalid JSON or not an object
3. Check 'contestant' field → 400 if missing
4. Check type is string     → 400 if not a string
5. Max length check (100)   → 400 if > 100 characters
6. Normalize name           → (trim, lowercase, strip non-alpha)
7. Empty check              → 400 if empty after normalization
8. Roster check             → 404 if not in contestant set
9. Check User-Agent header  → 422 if missing or empty
10. Compute fingerprint     → SHA-256(IP + User-Agent)
11. Insert vote into DB     → 409 if duplicate fingerprint
12. Return success          → 200
```

This order ensures that cheap checks run first and expensive operations (DB writes) run last.

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

## 9. Frontend Specification

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
6. On error (4xx): set `message` from `detail` field, `severity = "error"`.
7. After successful vote (`voted = true`): TextField and Button are disabled permanently for the session.
8. The Alert is only displayed when `message` is non-empty.

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
- `allow_origins=["*"]` (for development; tighten for production)
- `allow_methods=["POST"]`
- `allow_headers=["*"]`

---

## 10. Edge Cases

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
