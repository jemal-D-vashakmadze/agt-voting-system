"""AGT Voting System - FastAPI Backend."""

import asyncio
import hashlib
import ipaddress
import logging
import re
import time
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("agt")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)

# ---------------------------------------------------------------------------
# Pydantic model (documentation only - NOT used as route parameter)
# ---------------------------------------------------------------------------


class VoteRequest(BaseModel):
    contestant: str


# ---------------------------------------------------------------------------
# Contestant roster
# ---------------------------------------------------------------------------
CONTESTANTS: set[str] = {
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
CONTESTANTS_DISPLAY: str = ", ".join(
    name.capitalize() for name in sorted(CONTESTANTS)
)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
rate_limit_store: dict[str, list[float]] = {}
rate_limit_lock: asyncio.Lock = asyncio.Lock()
rate_limit_counter: int = 0


async def check_rate_limit(ip: str) -> bool:
    """Return True if the IP has exceeded the rate limit."""
    global rate_limit_counter
    async with rate_limit_lock:
        now = time.time()
        timestamps = rate_limit_store.get(ip, [])
        timestamps = [t for t in timestamps if now - t < 60]
        if len(timestamps) >= 10:
            rate_limit_store[ip] = timestamps
            return True
        timestamps.append(now)
        rate_limit_store[ip] = timestamps
        rate_limit_counter += 1
        if rate_limit_counter % 50 == 0:
            stale = [
                k
                for k, v in rate_limit_store.items()
                if all(now - t >= 60 for t in v)
            ]
            for k in stale:
                del rate_limit_store[k]
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_ip(raw_ip: str) -> str:
    addr = ipaddress.ip_address(raw_ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    return str(addr)


def normalize_name(raw: str) -> str:
    return re.sub(r"[^a-z]", "", raw.strip().lower())


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contestant TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    ip_address TEXT NOT NULL,
    user_agent TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await aiosqlite.connect("votes.db")
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute(CREATE_TABLE_SQL)
    await db.commit()
    app.state.db = db
    yield
    await db.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(lifespan=lifespan, debug=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    return JSONResponse(
        status_code=422, content={"detail": "Invalid request body."}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error."}
    )


# ---------------------------------------------------------------------------
# Vote endpoint
# ---------------------------------------------------------------------------
@app.post("/api/vote")
async def vote(request: Request):
    # 1. Check request.client
    if request.client is None:
        logger.warning("Validation error: Unable to determine client IP.")
        return JSONResponse(
            status_code=400,
            content={"detail": "Unable to determine client IP."},
        )

    raw_ip = request.client.host

    # 2. Rate limit
    try:
        norm_ip = normalize_ip(raw_ip)
    except ValueError:
        norm_ip = raw_ip

    if await check_rate_limit(norm_ip):
        logger.warning("Rate limit exceeded for IP")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
        )

    # 3. Parse JSON body manually
    try:
        body = await request.json()
    except Exception:
        logger.warning("Validation error: Invalid request body.")
        return JSONResponse(
            status_code=400, content={"detail": "Invalid request body."}
        )

    if not isinstance(body, dict):
        logger.warning("Validation error: Invalid request body.")
        return JSONResponse(
            status_code=400, content={"detail": "Invalid request body."}
        )

    # 4. Check 'contestant' field exists
    if "contestant" not in body:
        logger.warning(
            "Validation error: Missing required field: contestant."
        )
        return JSONResponse(
            status_code=422,
            content={"detail": "Missing required field: contestant."},
        )

    contestant_raw = body["contestant"]

    # 5. Check type is string
    if not isinstance(contestant_raw, str):
        logger.warning("Validation error: Contestant must be a string.")
        return JSONResponse(
            status_code=422,
            content={"detail": "Contestant must be a string."},
        )

    # 6. Max length check
    if len(contestant_raw) > 100:
        logger.warning(
            "Validation error: Input exceeds maximum length of 100 characters."
        )
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Input exceeds maximum length of 100 characters."
            },
        )

    # 7. Normalize name
    normalized = normalize_name(contestant_raw)

    # 8. Empty check
    if not normalized:
        logger.warning(
            "Validation error: Contestant name must not be empty."
        )
        return JSONResponse(
            status_code=400,
            content={"detail": "Contestant name must not be empty."},
        )

    # 9. Roster check
    if normalized not in CONTESTANTS:
        logger.warning(
            f"Validation error: Unknown contestant: '{normalized}'."
        )
        return JSONResponse(
            status_code=404,
            content={
                "detail": f"Unknown contestant: '{normalized}'. Valid contestants: {CONTESTANTS_DISPLAY}."
            },
        )

    # 10. Check User-Agent header
    user_agent = request.headers.get("user-agent", "")
    if not user_agent:
        logger.warning("Validation error: Missing User-Agent header.")
        return JSONResponse(
            status_code=422,
            content={"detail": "Missing User-Agent header."},
        )

    # 11. Normalize IP address
    try:
        normalized_ip = normalize_ip(raw_ip)
    except ValueError:
        normalized_ip = raw_ip

    # 12. Compute fingerprint
    fingerprint = hashlib.sha256(
        f"{normalized_ip}|{user_agent}".encode()
    ).hexdigest()

    # 13. Insert vote into DB
    try:
        db = request.app.state.db
        cursor = await db.execute(
            "INSERT OR IGNORE INTO votes (contestant, fingerprint, ip_address, user_agent) VALUES (?, ?, ?, ?)",
            (normalized, fingerprint, raw_ip, user_agent),
        )
        if cursor.rowcount == 0:
            logger.warning("Duplicate vote rejected")
            return JSONResponse(
                status_code=409,
                content={"detail": "You have already voted."},
            )
        await db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    # 14. Return success
    logger.info(f"Vote recorded: contestant={normalized}")
    return JSONResponse(
        status_code=200,
        content={
            "message": f"Vote recorded for {normalized.capitalize()}."
        },
    )
