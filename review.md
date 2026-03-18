# AGT Voting System — Red-Team Spec Review

---

## 1. Security Gaps

### 1.1 Fingerprint Concatenation Collision (No Separator)

- **Severity**: Critical
- **Issue**: The fingerprint is `SHA-256(ip_address + user_agent)` with no separator. This creates ambiguous boundaries. IP `"1.2.3.4"` + UA `"5Mozilla"` hashes identically to IP `"1.2.3.45"` + UA `"Mozilla"` — both concatenate to `"1.2.3.45Mozilla"`. Two distinct users produce the same fingerprint.
- **Impact**: Legitimate voter is falsely rejected with 409 "You have already voted" because a different user happened to produce a colliding concatenation. This is not a theoretical SHA-256 collision — it's a trivially constructible input collision *before* hashing.
- **Recommendation**: Use a non-ambiguous separator that cannot appear in either field. IP addresses cannot contain `|`, so use `SHA-256(ip_address + "|" + user_agent)`. Document the separator choice.

### 1.2 Fingerprint Trivially Bypassed by Changing User-Agent

- **Severity**: Critical
- **Issue**: The fingerprint is `SHA-256(IP + User-Agent)`. Any user can vote 10 times by sending 10 requests with different User-Agent strings (e.g., `curl -A "bot1"`, `curl -A "bot2"`, ...). This requires zero technical sophistication.
- **Impact**: The entire vote-integrity mechanism is defeated. The spec claims "one vote per device" but delivers "one vote per (IP, UA string) pair." A single person on a single device can trivially stuff the ballot.
- **Recommendation**: The brief accepts this as a "casual fraud" prevention measure, but the spec should explicitly acknowledge this limitation. If stronger integrity is needed, consider browser-fingerprinting libraries, cookie-based tokens, or CAPTCHA. At minimum, document the threat model boundary: "This prevents accidental double-votes but not intentional manipulation."

### 1.3 CORS Wildcard in Production

- **Severity**: High
- **Issue**: The spec says `allow_origins=["*"]` with the comment "(for development; tighten for production)" but provides no production configuration. A developer following the spec literally ships with `allow_origins=["*"]`.
- **Impact**: Any website on the internet can make cross-origin POST requests to the voting endpoint, enabling vote-stuffing scripts hosted on third-party domains.
- **Recommendation**: Specify the production CORS config explicitly: `allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")]`. Move the wildcard into a `DEBUG`-only code path.

### 1.4 Reverse Proxy Breaks Both Rate Limiting and Fingerprinting

- **Severity**: High
- **Issue**: The spec mandates `request.client.host` and explicitly prohibits `X-Forwarded-For`. Behind any reverse proxy (nginx, Cloudflare, AWS ALB), `request.client.host` returns the proxy's IP for *every* request. All users share the same IP component in the fingerprint and the same rate-limit bucket.
- **Impact**: (a) Rate limiting triggers after 10 total requests across all users — the entire service becomes unusable. (b) Fingerprint collisions skyrocket — most users sharing a proxy + common browser UA will be rejected as duplicates.
- **Recommendation**: Add a deployment section specifying: "If behind a reverse proxy, configure `--proxy-headers` in Uvicorn and use `X-Real-IP` or the first entry in `X-Forwarded-For` after validating the proxy is trusted." Alternatively, state explicitly that this system must be deployed without a reverse proxy.

### 1.5 No User-Agent Length Limit

- **Severity**: Medium
- **Issue**: User-Agent is stored raw in the database with no length check. The spec validates `contestant` length (100 chars) but applies no limit to User-Agent. An attacker can send a 10MB User-Agent header.
- **Impact**: (a) Database bloat — each vote could store megabytes of junk in `user_agent`. (b) SHA-256 must hash the entire string, consuming CPU. (c) SQLite row size becomes unpredictable.
- **Recommendation**: Add a User-Agent length check (e.g., reject if > 512 characters) as step 9.5, before fingerprint computation. Return 400 with `"User-Agent header too long."`.

### 1.6 No Request Body Size Limit

- **Severity**: Medium
- **Issue**: The spec enforces a 100-character limit on the `contestant` field but does not limit the overall request body size. A request like `{"contestant": "Thompson", "junk": "A" * 100000000}` would be accepted and parsed.
- **Impact**: Memory exhaustion on the server. FastAPI/Starlette will attempt to read and parse the entire body into memory before any validation runs.
- **Recommendation**: Specify a max request body size (e.g., 1KB) via middleware or server configuration. Starlette supports `--limit-request-body` via Uvicorn.

---

## 2. Race Conditions

### 2.1 In-Memory Rate Limiter Not Safe Across Workers

- **Severity**: High
- **Issue**: The rate limiter is a plain `dict[str, list[float]]` in process memory. If Uvicorn is started with `--workers N` (N > 1), each worker has its own independent dict. An attacker can send `10 * N` requests within 60 seconds without hitting the limit.
- **Impact**: Rate limiting is silently ineffective in any multi-worker deployment. The spec does not mention worker count or this limitation.
- **Recommendation**: Either (a) specify `--workers 1` as a deployment requirement, or (b) use a shared rate-limiting store (Redis, shared memory). At minimum, document the single-worker constraint.

### 2.2 SQLite Concurrent Write Contention

- **Severity**: Medium
- **Issue**: The spec does not mention SQLite journal mode. Default journal mode (`DELETE`) locks the entire database on writes. Under concurrent requests, writers will block each other, and `sqlite3.OperationalError: database is locked` will be raised after the default 5-second timeout.
- **Impact**: Under moderate load, legitimate votes fail with unhandled 500 errors. No error response is specified for this scenario.
- **Recommendation**: (a) Enable WAL mode: `PRAGMA journal_mode=WAL;` at connection setup. (b) Set a busy timeout: `PRAGMA busy_timeout=5000;`. (c) Specify an error response for transient DB failures (e.g., 503 Service Unavailable).

### 2.3 Rate Limiter Dict Mutation During Async Iteration

- **Severity**: Low
- **Issue**: In a single-worker async FastAPI setup, the event loop is single-threaded, so `dict` operations are generally safe. However, if anyone wraps the rate-limiter logic in `run_in_executor` or uses threading, the plain `dict` and `list` mutations are not thread-safe — leading to lost updates or corrupted state.
- **Impact**: Low risk in the standard async deployment, but the spec's silence on thread safety is a trap for developers who might "optimize" the design.
- **Recommendation**: Add a note: "The rate limiter assumes single-threaded async execution. Do not use with threaded workers or `run_in_executor`."

---

## 3. Missing Edge Cases

### 3.1 `request.client` Is None

- **Severity**: High
- **Issue**: In ASGI, `request.client` can be `None` (e.g., when running behind certain proxies or in testing). The spec directs developers to use `request.client.host`, which raises `AttributeError: 'NoneType' object has no attribute 'host'` when `request.client` is `None`.
- **Impact**: Unhandled 500 error. The server crashes on every request in deployments where `request.client` is not populated.
- **Recommendation**: Add an explicit check: if `request.client` is `None`, return 400 with `"Unable to determine client IP."` Or specify it as a deployment precondition.

### 3.2 IPv4 vs. IPv6 Inconsistency

- **Severity**: Medium
- **Issue**: The same machine connecting via IPv4 (`127.0.0.1`) vs. IPv6 (`::1`) produces different fingerprints. A user who votes over IPv4 can vote again if their connection switches to IPv6 (dual-stack networks).
- **Impact**: Duplicate votes from the same device, undermining vote integrity.
- **Recommendation**: Normalize the IP: if it's an IPv4-mapped IPv6 address (e.g., `::ffff:127.0.0.1`), extract the IPv4 portion before hashing. Document the expected IP format.

### 3.3 Spec Worked Example Error: "Martínez" Listed as Valid

- **Severity**: Medium
- **Issue**: The normalization worked examples table (Section 4) shows `"Martínez"` → `"martnez"` with result "Valid." But `"martnez"` is NOT in the CONTESTANTS set (`"martinez"` is). The accented `í` is stripped by `[^a-z]`, removing the letter entirely. The result should be "Not Found," not "Valid."
- **Impact**: A developer trusting the spec table will implement special Unicode handling (e.g., `unidecode`) to make this case work, diverging from the normalization algorithm described. Alternatively, a developer following the algorithm will produce behavior contradicting the table — both paths cause confusion.
- **Recommendation**: Fix the table. Either: (a) change the result to "Not Found" (matching the algorithm as written), or (b) add a Unicode normalization step (e.g., NFKD decomposition to strip accents before the regex) and update the algorithm.

### 3.4 Non-ASCII Letters Silently Dropped

- **Severity**: Medium
- **Issue**: The regex `[^a-z]` strips ALL non-ASCII letters: accented characters (é, ñ, ü), Cyrillic, CJK, etc. A user typing on a non-US keyboard may unknowingly produce accented characters that silently mutate the name (e.g., `"Martínez"` → `"martnez"` ≠ `"martinez"`).
- **Impact**: Legitimate voters are rejected with a confusing "Unknown contestant" error. The user typed the right name but their keyboard layout introduced an accent.
- **Recommendation**: Add a Unicode NFKD normalization step before the regex strip: `unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')`. This converts `í` → `i` before stripping.

---

## 4. Over-Engineering

### 4.1 Unnecessary PII Storage (IP Address and User-Agent)

- **Severity**: Medium
- **Issue**: The schema stores raw `ip_address` and `user_agent` as separate columns. The only operational use of these values is to compute the fingerprint hash, which is also stored. The raw values are never queried, displayed, or used after insertion.
- **Impact**: Unnecessary PII retention. Creates GDPR/privacy liability. If the database is breached, attacker obtains IP addresses and browser fingerprints for every voter. The brief doesn't require any functionality that needs these raw values.
- **Recommendation**: Store only the `fingerprint` hash. Remove `ip_address` and `user_agent` columns. If debugging is needed, log (don't persist) these values temporarily.

### 4.2 AUTOINCREMENT on `id`

- **Severity**: Low
- **Issue**: `AUTOINCREMENT` in SQLite prevents reuse of ROWIDs from deleted rows. Since votes are never deleted, this is functionally identical to the default ROWID behavior but adds overhead (SQLite maintains an internal `sqlite_sequence` table).
- **Impact**: Negligible performance cost, but adds complexity for no benefit.
- **Recommendation**: Use `id INTEGER PRIMARY KEY` without `AUTOINCREMENT`. SQLite will still auto-assign incrementing IDs.

---

## 5. Under-Engineering

### 5.1 No Application Logging

- **Severity**: High
- **Issue**: The spec excludes "analytics or logging endpoint" but provides no application-level logging whatsoever. No request logging, no error logging, no audit trail.
- **Impact**: When something goes wrong (500 errors, DB corruption, suspected abuse), there is zero visibility. Debugging requires reproducing the issue blind. Vote manipulation goes undetected.
- **Recommendation**: Add structured logging (Python `logging` module) for: (a) every vote attempt (contestant, fingerprint, result status), (b) rate-limit triggers, (c) DB errors, (d) startup/shutdown events. Do NOT log raw IP or User-Agent (privacy). Log the fingerprint hash only.

### 5.2 No Database Connection Lifecycle Management

- **Severity**: High
- **Issue**: The spec does not address how SQLite connections are created, shared, or closed. No mention of FastAPI `lifespan`, dependency injection for DB connections, or connection cleanup.
- **Impact**: A developer might: (a) create a global connection (not thread-safe with SQLite), (b) create a new connection per request and forget to close it (resource leak), (c) share a connection across async tasks (corruption risk). All three are common mistakes with SQLite + FastAPI.
- **Recommendation**: Specify the connection pattern. For SQLite + async FastAPI, recommend: create a connection per request using a FastAPI dependency, with `try/finally` to ensure close. Run `CREATE TABLE IF NOT EXISTS` and `PRAGMA journal_mode=WAL` at app startup via the `lifespan` context manager.

### 5.3 No Error Handling for Database Failures

- **Severity**: Medium
- **Issue**: The spec only handles `IntegrityError` (duplicate fingerprint → 409). No other database exceptions are caught or specified: `OperationalError` (locked DB, disk full), `DatabaseError` (corruption), permission errors.
- **Impact**: Any DB failure other than duplicate key results in an unhandled 500 with a Python traceback in the response (information leakage) or a generic FastAPI error.
- **Recommendation**: Add a catch-all for `sqlite3.Error` that returns 503 with `{"detail": "Service temporarily unavailable."}` and logs the error. Never expose tracebacks.

### 5.4 Rate Limiter Memory Leak Under Distributed Attack

- **Severity**: Medium
- **Issue**: The rate limiter only cleans timestamps for an IP when that same IP makes a new request. If 1 million unique IPs each send one request, the dict holds 1 million entries with one timestamp each, forever. These entries are never cleaned because those IPs never return.
- **Impact**: Memory grows linearly with unique attacking IPs. A distributed botnet sending single requests from unique IPs will eventually exhaust server memory.
- **Recommendation**: Add periodic cleanup. Either: (a) run a background task every 60 seconds to evict stale entries, or (b) use an LRU-based structure (e.g., `cachetools.TTLCache`) that automatically expires entries.

### 5.5 No Database Initialization Timing Specified

- **Severity**: Low
- **Issue**: The spec provides the `CREATE TABLE IF NOT EXISTS` DDL but does not say when to execute it — at import time, app startup, first request, or in a separate migration script.
- **Impact**: A developer might run it on every request (wasteful), at import time (connection leaks), or forget it entirely (crash on first vote).
- **Recommendation**: Specify: "Execute `CREATE TABLE IF NOT EXISTS` once during application startup, in the FastAPI `lifespan` context manager."

---

## 6. Data Model Issues

### 6.1 Missing Index on `ip_address`

- **Severity**: Low
- **Issue**: The `ip_address` column has no index. While rate limiting is in-memory, if the system ever needs to query votes by IP (abuse investigation, GDPR deletion requests), it would require a full table scan.
- **Impact**: Minimal for current spec (no query endpoints), but creates technical debt if requirements grow.
- **Recommendation**: If `ip_address` is retained (see 4.1), add `CREATE INDEX idx_votes_ip ON votes(ip_address);`. If removed per 4.1, this is moot.

### 6.2 `created_at` Timezone Ambiguity

- **Severity**: Low
- **Issue**: `CURRENT_TIMESTAMP` in SQLite produces UTC in format `"YYYY-MM-DD HH:MM:SS"`. The spec does not state this is UTC, nor does it specify the format. A developer might assume local time or ISO 8601 format with timezone offset.
- **Impact**: Timestamps may be misinterpreted if the server timezone differs from the expected display timezone.
- **Recommendation**: Document: "`created_at` stores UTC timestamps in ISO 8601 format." Consider storing as Unix epoch (integer) for unambiguous timezone handling.

### 6.3 Contestant Stored Lowercase, Displayed Capitalized

- **Severity**: Low
- **Issue**: The column stores `"thompson"` (lowercase) but the success response shows `"Thompson"` (capitalized via `.capitalize()`). The spec doesn't explicitly say to use `.capitalize()` on the stored value for the response — it says `<normalized_name>` is "capitalized" but the normalized name is lowercase.
- **Impact**: Minor ambiguity. Developer may return lowercase name in the success message.
- **Recommendation**: Explicitly state: "In the 200 response, apply `.capitalize()` to the normalized name before inserting into the message string."

---

## 7. Frontend Concerns

### 7.1 Hardcoded Contestant List Creates Sync Risk

- **Severity**: Medium
- **Issue**: The contestant list is hardcoded in both the backend (Python set) and the frontend (static text). There is no API endpoint to fetch the list. If the roster changes, both files must be updated manually.
- **Impact**: If a developer updates one side but not the other, the frontend shows stale names. Users see "Valid contestants: X" but voting for X returns 404.
- **Recommendation**: Either (a) add a `GET /api/contestants` endpoint to serve the roster (adds scope but eliminates sync risk), or (b) document clearly: "The contestant list MUST be identical in both backend and frontend. Any roster change requires updating both."

### 7.2 `voted` State Resets on Page Refresh

- **Severity**: Medium
- **Issue**: The `voted` state is `useState(false)` — React component state that resets on page refresh. After voting, the user refreshes and sees an enabled form again. They submit and get a 409 error.
- **Impact**: Confusing UX. The user sees "You have already voted" but the form appeared to invite them to vote. The "permanently disabled" claim (spec Section 9) is misleading — it's session-only in the weakest sense.
- **Recommendation**: Persist `voted` state in `localStorage`. On mount, check `localStorage` and disable the form if the user already voted. This doesn't prevent clearing localStorage, but it provides a much better UX for honest users.

### 7.3 No Accessibility Specification

- **Severity**: Medium
- **Issue**: The spec mentions MUI components but does not address: ARIA labels, focus management after submission, screen reader announcements for the Alert, keyboard navigation, color contrast requirements.
- **Impact**: The application may be inaccessible to users with disabilities. Potential legal liability (ADA, WCAG compliance).
- **Recommendation**: Specify: (a) `aria-live="polite"` on the Alert region, (b) focus moves to the Alert after submission, (c) Button has `aria-label` when in loading state, (d) require WCAG 2.1 AA color contrast.

### 7.4 Fallback API URL Will Break in Production

- **Severity**: Medium
- **Issue**: `const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`. If the environment variable is not set in production, all API calls go to `localhost:8000` — which doesn't exist on the production server (or worse, hits an unrelated service).
- **Impact**: Complete application failure in production if the env var is misconfigured. No error is shown — requests silently fail or hit the wrong service.
- **Recommendation**: Remove the fallback. If `NEXT_PUBLIC_API_URL` is undefined, throw an error at build time or render an error state. The localhost default is dangerous.

### 7.5 No Error Handling for Network Failures

- **Severity**: Low
- **Issue**: The spec defines behavior for 4xx responses but not for network errors (timeout, DNS failure, server unreachable). The frontend behavior when `fetch()` throws a `TypeError` or the request times out is unspecified.
- **Impact**: User clicks "Vote," the request fails due to network issues, and the UI either hangs in loading state or shows an uncaught error.
- **Recommendation**: Specify: "On network error (fetch rejects), set `message` to `'Network error. Please try again.'` and `severity` to `'error'`. Set `loading = false`."

---

## 8. Spec Ambiguities

### 8.1 Pydantic Model Usage Not Specified — Conflicting Error Formats

- **Severity**: Critical
- **Issue**: FastAPI's standard approach is to define a Pydantic request model (e.g., `class VoteRequest(BaseModel): contestant: str`). If a developer does this, FastAPI auto-validates and returns its own 422 response format: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`. This conflicts with the spec's custom 400 errors (simple `{"detail": "string"}` format). The spec does not mention Pydantic at all, nor does it tell the developer to avoid FastAPI's automatic validation. The processing order (Section 7) implies manual JSON parsing, but this contradicts idiomatic FastAPI usage.
- **Impact**: A developer using Pydantic (the natural FastAPI choice) will produce different HTTP status codes (422 instead of 400) and different error response formats (array of objects instead of a single string). The application will technically work but fail every integration test that checks error formats.
- **Recommendation**: Add an explicit note: "Do NOT use a Pydantic request model. Parse the request body manually using `await request.json()` with a try/except for `JSONDecodeError`. Perform field validation manually to produce the exact error responses specified." Provide a code skeleton.

### 8.2 Processing Order Makes User-Agent Check Position Illogical

- **Severity**: Medium
- **Issue**: User-Agent is checked at step 9, after contestant validation (steps 3-8). This means a request with no User-Agent and an invalid contestant returns 400/404 (contestant error), not 422 (missing User-Agent). The actual infrastructure problem (missing header) is masked by an input validation error. A client debugging a missing User-Agent issue will see misleading errors until they also fix their contestant input.
- **Impact**: Debugging confusion. The spec says this ordering puts "cheap checks first," but a string-empty check on a header is cheaper than name normalization + set lookup.
- **Recommendation**: Move User-Agent check to step 2 (after rate limiting, before body parsing). A request without User-Agent should always fail with 422 regardless of body content.

### 8.3 Undefined Behavior for Extra JSON Fields

- **Severity**: Low
- **Issue**: The spec does not say what happens if the request body contains extra fields: `{"contestant": "Thompson", "extra": "data"}`. Should extra fields be ignored? Rejected?
- **Impact**: Without guidance, developers make inconsistent choices. If using manual parsing, extra fields are silently ignored. If using Pydantic with `model_config = {"extra": "forbid"}`, they're rejected.
- **Recommendation**: State explicitly: "Extra fields in the JSON body are ignored."

### 8.4 Uvicorn / Deployment Configuration Unspecified

- **Severity**: Low
- **Issue**: No guidance on Uvicorn host, port, worker count, or reload settings. The only implicit hint is port 8000 (from the frontend fallback URL).
- **Impact**: Developer may use multiple workers (breaks rate limiter — see 2.1) or bind to wrong interface.
- **Recommendation**: Add a deployment section: "Run with `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1`. Single worker is required for the in-memory rate limiter."

---

## Summary: Critical and High Findings

| # | Severity | Finding | Section |
|---|----------|---------|---------|
| 1.1 | **Critical** | Fingerprint concatenation without separator causes false collisions between different users | Security |
| 1.2 | **Critical** | Fingerprint trivially bypassed by changing User-Agent string | Security |
| 8.1 | **Critical** | Pydantic model unspecified — developer will produce wrong status codes and error formats | Ambiguity |
| 1.3 | **High** | CORS wildcard `*` has no production override — any domain can submit votes | Security |
| 1.4 | **High** | Deployment behind reverse proxy breaks both rate limiting and fingerprinting | Security |
| 2.1 | **High** | In-memory rate limiter fails silently with multiple Uvicorn workers | Race Condition |
| 3.1 | **High** | `request.client` can be `None` — causes unhandled 500 error | Edge Case |
| 5.1 | **High** | No application logging — zero operational visibility | Under-Engineering |
| 5.2 | **High** | No DB connection lifecycle — resource leaks and corruption risk | Under-Engineering |
