# Completeness Matrix

| Requirement | Status | Evidence |
|---|---|---|
| POST /api/vote endpoint | ✅ Done | `backend/main.py:167` `@app.post("/api/vote")`; test: `test_successful_vote` |
| Request body: Pydantic model as docs only, not route param | ✅ Done | `backend/main.py:35-36` `class VoteRequest(BaseModel)` defined; route uses `Request` not model (`main.py:168`); body parsed manually (`main.py:194`) |
| Manual JSON parsing (not FastAPI auto-validation) | ✅ Done | `backend/main.py:193-205` `await request.json()` in try/except; per spec §7 step 3 |
| Name normalization: trim + lowercase + strip non-alpha | ✅ Done | `backend/main.py:100-101` `re.sub(r"[^a-z]", "", raw.strip().lower())`; tests: `test_case_upper`, `test_case_lower`, `test_case_mixed`, `test_special_chars_normalized`, `test_hyphens_stripped` |
| Contestant roster: 10 names as lowercase set | ✅ Done | `backend/main.py:42-53` `CONTESTANTS` set with 10 entries; `main.py:54-56` `CONTESTANTS_DISPLAY` sorted/capitalized |
| Contestant display string (alpha sorted, capitalized) | ✅ Done | `backend/main.py:54-56`; `frontend/src/app/page.tsx:10-11`; test: `test_unknown_contestant` verifies display in 404 |
| Device fingerprint: SHA-256(ip + "\|" + user_agent) | ✅ Done | `backend/main.py:280-282` `hashlib.sha256(f"{normalized_ip}\|{user_agent}".encode()).hexdigest()` |
| IP normalization: IPv6-mapped → IPv4 | ✅ Done | `backend/main.py:93-97` `normalize_ip()` using `ipaddress` module; used at `main.py:181` and `main.py:275` |
| Duplicate vote prevention: INSERT OR IGNORE + rowcount | ✅ Done | `backend/main.py:288-296` `INSERT OR IGNORE` + `cursor.rowcount == 0` → 409; test: `test_duplicate_vote` |
| fingerprint column UNIQUE constraint | ✅ Done | `backend/main.py:111` `fingerprint TEXT NOT NULL UNIQUE` |
| One vote per fingerprint (not per contestant) | ✅ Done | `backend/main.py:288-296`; test: `test_duplicate_vote` votes same contestant twice → 409 |
| Rate limiting: 10/min per IP | ✅ Done | `backend/main.py:66-87` `check_rate_limit()`; 60s window, ≥10 threshold; test: `test_rate_limiting` |
| Rate limiting: asyncio.Lock | ✅ Done | `backend/main.py:62` `rate_limit_lock = asyncio.Lock()`; acquired at `main.py:69` |
| Rate limiting: in-memory dict | ✅ Done | `backend/main.py:61` `rate_limit_store: dict[str, list[float]] = {}` |
| Rate limiting: periodic sweep every 50 requests | ✅ Done | `backend/main.py:78-86` counter check `% 50`, removes stale entries |
| Rate limiting: uses normalized IP as key | ✅ Done | `backend/main.py:181-185` `normalize_ip(raw_ip)` passed to `check_rate_limit()` |
| Input sanitization: max 100 chars (before normalization) | ✅ Done | `backend/main.py:228-237` `len(contestant_raw) > 100` → 400; test: `test_input_too_long` |
| Input sanitization: empty after normalization | ✅ Done | `backend/main.py:243-250` `if not normalized` → 400; tests: `test_empty_input`, `test_whitespace_only`, `test_special_chars_only`, `test_digits_only` |
| SQL injection prevention: parameterized queries | ✅ Done | `backend/main.py:288-289` uses `?` placeholders; test: `test_sql_injection` |
| XSS prevention: normalization strips non-alpha | ✅ Done | `backend/main.py:101` `[^a-z]` regex; test: `test_xss_attempt` |
| Error 400: no client IP | ✅ Done | `backend/main.py:170-175` `request.client is None` → 400 `"Unable to determine client IP."` |
| Error 400: invalid JSON body | ✅ Done | `backend/main.py:193-205` try/except + dict check → 400 `"Invalid request body."` |
| Error 400: missing contestant field | ⚠️ Mismatch | Spec §1 says 400; `backend/main.py:212-215` returns **422**; test `test_missing_field` asserts 422 |
| Error 400: invalid contestant type | ⚠️ Mismatch | Spec §1 says 400; `backend/main.py:222-225` returns **422**; tests `test_null_value`, `test_non_string_type` assert 422 |
| Error 400: input too long | ✅ Done | `backend/main.py:228-237` → 400; test: `test_input_too_long` |
| Error 400: empty after normalization | ✅ Done | `backend/main.py:243-250` → 400; tests: `test_empty_input`, `test_whitespace_only`, `test_special_chars_only`, `test_digits_only` |
| Error 404: unknown contestant | ✅ Done | `backend/main.py:253-262` → 404 with display list; test: `test_unknown_contestant` |
| Error 409: duplicate vote | ✅ Done | `backend/main.py:291-296` → 409 `"You have already voted."`; test: `test_duplicate_vote` |
| Error 422: missing User-Agent | ✅ Done | `backend/main.py:265-271` → 422; test: `test_missing_user_agent` |
| Error 429: rate limit exceeded | ✅ Done | `backend/main.py:185-190` → 429; test: `test_rate_limiting` |
| Error 500: database error | ✅ Done | `backend/main.py:298-303` catches Exception → 500 `"Internal server error."`; generic handler at `main.py:156-161` |
| Processing order: 14 steps in spec §7 order | ✅ Done | `backend/main.py:169-312` steps 1–14 match spec order (client→rate→json→field→type→length→normalize→empty→roster→UA→IP→fingerprint→insert→success) |
| CORS: localhost:3000 + 127.0.0.1:3000, POST, Content-Type | ✅ Done | `backend/main.py:136-141` `CORSMiddleware` with exact origins, methods, headers |
| Custom validation error handler | ✅ Done | `backend/main.py:147-153` `@app.exception_handler(RequestValidationError)` → 422 |
| Generic exception handler | ✅ Done | `backend/main.py:156-161` `@app.exception_handler(Exception)` → 500 |
| debug=False | ✅ Done | `backend/main.py:134` `FastAPI(lifespan=lifespan, debug=False)` |
| Logging: logger named "agt" at INFO | ✅ Done | `backend/main.py:21-28` `logging.getLogger("agt")`, `logger.setLevel(logging.INFO)` |
| Logging: vote recorded (INFO) | ✅ Done | `backend/main.py:306` `logger.info(f"Vote recorded: contestant={normalized}")` |
| Logging: duplicate rejected (WARNING) | ✅ Done | `backend/main.py:292` `logger.warning("Duplicate vote rejected")` |
| Logging: rate limit exceeded (WARNING) | ✅ Done | `backend/main.py:186` `logger.warning("Rate limit exceeded for IP")` |
| Logging: validation errors (WARNING) | ✅ Done | `backend/main.py:171,196,203,209,221,229,244,254` — all validation paths log warnings |
| Logging: database error (ERROR) | ✅ Done | `backend/main.py:299` `logger.error(f"Database error: {e}")` |
| Logging: no raw IPs logged | ✅ Done | All log messages use `"IP"` placeholder or omit IP entirely |
| Database lifespan: open at startup, close at shutdown | ✅ Done | `backend/main.py:119-128` `lifespan()` async context manager; connect → yield → close |
| SQLite WAL mode | ✅ Done | `backend/main.py:122` `PRAGMA journal_mode=WAL` |
| SQLite busy_timeout=5000 | ✅ Done | `backend/main.py:123` `PRAGMA busy_timeout=5000` |
| CREATE TABLE in lifespan startup | ✅ Done | `backend/main.py:124` `await db.execute(CREATE_TABLE_SQL)` |
| Database schema matches spec §2 | ✅ Done | `backend/main.py:107-116` matches spec (id, contestant, fingerprint UNIQUE, ip_address, user_agent, created_at) |
| Normalized IP used for fingerprint, raw IP stored in DB | ✅ Done | `backend/main.py:281` fingerprint uses `normalized_ip`; `main.py:289` stores `raw_ip` in ip_address column |
| Success response: capitalized name | ✅ Done | `backend/main.py:310` `normalized.capitalize()`; test: `test_successful_vote` asserts `"Vote recorded for Thompson."` |
| Frontend: "use client" directive | ✅ Done | `frontend/src/app/page.tsx:1` `"use client"` |
| Frontend: MUI TextField (label, fullWidth) | ✅ Done | `frontend/src/app/page.tsx:63-68` `<TextField label="Contestant Last Name" fullWidth>`; test: `renders title, contestant list, and form controls` |
| Frontend: MUI Button (variant=contained, text=Vote) | ✅ Done | `frontend/src/app/page.tsx:71-77` `<Button variant="contained">`; test: `renders title, contestant list, and form controls` |
| Frontend: MUI Alert (severity bound to state) | ✅ Done | `frontend/src/app/page.tsx:80-84` `<Alert severity={severity}>`; tests: `successful vote shows green alert`, `404 error shows red alert` |
| Frontend: contestant list displayed | ✅ Done | `frontend/src/app/page.tsx:58-60` `"Valid contestants: {CONTESTANTS}"`; test: `renders title, contestant list, and form controls` |
| Frontend: form disabled after success (voted=true) | ✅ Done | `frontend/src/app/page.tsx:67,74` `disabled={loading \|\| voted}`; test: `successful vote shows green alert and disables form` |
| Frontend: env var for API URL | ✅ Done | `frontend/src/app/page.tsx:8` `process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000"` |
| Frontend: 5 state variables per spec | ✅ Done | `frontend/src/app/page.tsx:14-18` contestant, loading, message, severity, voted |
| Frontend: POST to /api/vote with {contestant} | ✅ Done | `frontend/src/app/page.tsx:26-30`; test: `correct API request sent` |
| Frontend: success → message + severity + voted + clear | ✅ Done | `frontend/src/app/page.tsx:34-38`; test: `input preserved on error, cleared on success` |
| Frontend: error → detail message + severity=error | ✅ Done | `frontend/src/app/page.tsx:40-41`; tests: `404 error shows red alert`, `409 error shows red alert`, `429 error shows red alert` |
| Frontend: network error → "Network error. Please try again." | ✅ Done | `frontend/src/app/page.tsx:43-44`; test: `network error shows red alert` |
| Frontend: Alert shown only when message non-empty | ✅ Done | `frontend/src/app/page.tsx:80` `{message && ...}` |
| Frontend: loading state during request | ✅ Done | `frontend/src/app/page.tsx:22,46-48` setLoading true/false in try/finally |
| Decision 1.1: fingerprint pipe separator | ✅ Done | `backend/main.py:281` `f"{normalized_ip}\|{user_agent}"` |
| Decision 8.1: manual JSON parsing, Pydantic as docs | ✅ Done | `backend/main.py:35-36` model defined; `main.py:168` route takes `Request`; `main.py:194` `request.json()` |
| Decision 1.3: CORS locked to localhost origins | ✅ Done | `backend/main.py:138` `["http://localhost:3000", "http://127.0.0.1:3000"]` |
| Decision 2.1: asyncio.Lock + single-worker documented | ✅ Done | `backend/main.py:62` Lock; single-worker in README |
| Decision 3.1: request.client None → 400 | ✅ Done | `backend/main.py:170-175` |
| Decision 5.1: Python logging, no raw IPs | ✅ Done | `backend/main.py:21-28` logger; all messages redact IPs |
| Decision 5.2: FastAPI lifespan for DB | ✅ Done | `backend/main.py:119-128` |
| Decision 2.2: WAL + busy_timeout | ✅ Done | `backend/main.py:122-123` |
| Decision 3.2: IPv6→IPv4 normalization | ✅ Done | `backend/main.py:93-97` |
| Decision 3.3: Martínez → "martnez" → Not Found | ✅ Done | `backend/main.py:101` regex strips í; spec §4 table updated |
| Decision 5.3: DB error → 500, no tracebacks | ✅ Done | `backend/main.py:298-303` catches Exception → generic 500 |
| Decision 5.4: rate limiter stale sweep every 50 req | ✅ Done | `backend/main.py:78-86` |
| Decision 5.5: CREATE TABLE in lifespan startup | ✅ Done | `backend/main.py:124` |
| Decision 7.5: frontend network error handling | ✅ Done | `frontend/src/app/page.tsx:43-44`; test: `network error shows red alert` |
| Different devices same contestant → both succeed | ✅ Done | test: `test_different_devices_same_contestant` (`tests/test_backend.py:228-241`) |
| Non-features excluded (no admin, tally, dashboard, etc.) | ✅ Done | No additional endpoints beyond `/api/vote`; single-page frontend |

## Deviations

| Issue | Spec Says | Implementation Does | Files |
|---|---|---|---|
| Missing contestant field status code | 400 Bad Request | 422 Unprocessable Entity | `backend/main.py:212-215`, `tests/test_backend.py:168` |
| Invalid contestant type status code | 400 Bad Request | 422 Unprocessable Entity | `backend/main.py:222-225`, `tests/test_backend.py:177,186` |
| Database driver | `sqlite3` (sync) | `aiosqlite` (async) | `backend/main.py:121` — functionally equivalent, async-native |
