# Red-Team Review Decisions

Triage of findings from `review.md`. Changes from accepted items have been applied to `spec.md`.

## Accepted

| ID   | Finding                          | Severity | Resolution                                                    |
|------|----------------------------------|----------|---------------------------------------------------------------|
| 1.1  | Fingerprint separator missing    | Critical | Use `SHA-256(ip + "\|" + user_agent)` with pipe delimiter      |
| 8.1  | Pydantic ambiguity               | Critical | Parse body manually with `request.json()`; keep Pydantic model as docs only |
| 1.3  | CORS wildcard                    | High     | Lock origins to `http://localhost:3000` and `http://127.0.0.1:3000` |
| 2.1  | Rate limiter multi-worker        | High     | Add `asyncio.Lock`; document `--workers 1` requirement        |
| 3.1  | `request.client` is None         | High     | Return 400 with clear message if None                         |
| 5.1  | No logging                       | High     | Python `logging` at INFO/WARNING; no raw IPs                  |
| 5.2  | DB connection lifecycle           | High     | FastAPI lifespan: open at startup, close at shutdown           |
| 2.2  | SQLite WAL mode                  | Medium   | Add `PRAGMA journal_mode=WAL` and `busy_timeout=5000`         |
| 3.2  | IPv4 vs IPv6                     | Medium   | Normalize with `ipaddress` module before fingerprinting        |
| 3.3  | Martínez example wrong           | Medium   | Fixed table: `"martnez"` → Not Found                          |
| 5.3  | No DB error handling             | Medium   | Catch exceptions, return 500, never expose tracebacks          |
| 5.4  | Rate limiter memory leak         | Medium   | Sweep stale entries every 50 requests                          |
| 5.5  | DB init timing                   | Low      | `CREATE TABLE` runs in lifespan startup                        |
| 7.5  | Network error handling           | Low      | Frontend shows "Network error. Please try again." on fetch failure |

## Rejected

| ID   | Finding                          | Severity | Reason                                                        |
|------|----------------------------------|----------|---------------------------------------------------------------|
| 1.2  | Fingerprint bypassable via UA    | Critical | Threat model is "casual fraud" not determined attackers        |
| 1.4  | Reverse proxy breaks things      | High     | Local dev app; no reverse proxy in scope                       |
| 1.5  | User-Agent length limit          | Medium   | Impractical attack vector for a voting demo                    |
| 1.6  | Request body size limit          | Medium   | FastAPI/Uvicorn defaults are sufficient                        |
| 2.3  | Dict mutation thread safety      | Medium   | Single-threaded async; covered by asyncio.Lock from 2.1       |
| 3.4  | Non-ASCII letter handling        | Medium   | All 10 contestants have ASCII names                            |
| 4.1  | Remove IP/UA from schema         | Medium   | Needed for debugging; no GDPR for a demo                       |
| 4.2  | Remove AUTOINCREMENT             | Low      | No meaningful impact                                           |
| 6.1  | Index on ip_address              | Low      | No query endpoints; < 100 rows expected                        |
| 6.2  | Timestamp timezone               | Low      | Internal storage only; no API reads                            |
| 6.3  | Capitalize in response           | Low      | Return lowercase as stored                                     |
| 7.1  | Contestant list sync risk        | Medium   | 10 hardcoded names; updating two files is fine                 |
| 7.2  | Persist voted in localStorage    | Medium   | 409 message is sufficient feedback                             |
| 7.3  | Accessibility                    | Medium   | MUI handles baseline accessibility                             |
| 7.4  | Remove localhost fallback        | Low      | Fallback is the point of local dev                             |
| 8.2  | Move User-Agent check earlier    | Low      | Empty string fallback; current order is fine                   |
| 8.3  | Extra JSON fields                | Low      | Ignored by default; correct behavior                           |
| 8.4  | Deployment config                | Low      | Covered by README single-worker note                           |
