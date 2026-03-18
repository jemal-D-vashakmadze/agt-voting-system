"""Tests for AGT Voting System backend."""

import asyncio

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

import backend.main as backend_module
from backend.main import CREATE_TABLE_SQL, app


@pytest.fixture
async def client():
    """Create a test client with a fresh in-memory database."""
    # Reset rate limiter state
    backend_module.rate_limit_store.clear()
    backend_module.rate_limit_counter = 0
    backend_module.rate_limit_lock = asyncio.Lock()

    # Set up in-memory database
    db = await aiosqlite.connect(":memory:")
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute(CREATE_TABLE_SQL)
    await db.commit()
    app.state.db = db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await db.close()


# --- Successful vote ---


async def test_successful_vote(client):
    r = await client.post("/api/vote", json={"contestant": "Thompson"})
    assert r.status_code == 200
    assert r.json() == {"message": "Vote recorded for Thompson."}


# --- Case insensitive ---


async def test_case_upper(client):
    r = await client.post("/api/vote", json={"contestant": "CHEN"})
    assert r.status_code == 200
    assert r.json() == {"message": "Vote recorded for Chen."}


async def test_case_lower(client):
    r = await client.post("/api/vote", json={"contestant": "chen"})
    assert r.status_code == 200
    assert r.json() == {"message": "Vote recorded for Chen."}


async def test_case_mixed(client):
    r = await client.post("/api/vote", json={"contestant": "cHeN"})
    assert r.status_code == 200
    assert r.json() == {"message": "Vote recorded for Chen."}


# --- Special chars normalized ---


async def test_special_chars_normalized(client):
    r = await client.post("/api/vote", json={"contestant": "O'Kafor"})
    assert r.status_code == 200
    assert r.json() == {"message": "Vote recorded for Okafor."}


# --- Hyphens stripped ---


async def test_hyphens_stripped(client):
    r = await client.post("/api/vote", json={"contestant": "na-ka-mu-ra"})
    assert r.status_code == 200
    assert r.json() == {"message": "Vote recorded for Nakamura."}


# --- Unknown contestant -> 404 ---


async def test_unknown_contestant(client):
    r = await client.post("/api/vote", json={"contestant": "yamamoto"})
    assert r.status_code == 404
    assert "Unknown contestant" in r.json()["detail"]
    assert "yamamoto" in r.json()["detail"]


# --- Empty input -> 400 ---


async def test_empty_input(client):
    r = await client.post("/api/vote", json={"contestant": ""})
    assert r.status_code == 400
    assert r.json()["detail"] == "Contestant name must not be empty."


# --- Whitespace only -> 400 ---


async def test_whitespace_only(client):
    r = await client.post("/api/vote", json={"contestant": "   "})
    assert r.status_code == 400
    assert r.json()["detail"] == "Contestant name must not be empty."


# --- Special chars only -> 400 ---


async def test_special_chars_only(client):
    r = await client.post("/api/vote", json={"contestant": "!@#$%^&*()"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Contestant name must not be empty."


# --- Digits only -> 400 ---


async def test_digits_only(client):
    r = await client.post("/api/vote", json={"contestant": "12345"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Contestant name must not be empty."


# --- Duplicate vote -> 409 ---


async def test_duplicate_vote(client):
    await client.post("/api/vote", json={"contestant": "Thompson"})
    r = await client.post("/api/vote", json={"contestant": "Thompson"})
    assert r.status_code == 409
    assert r.json()["detail"] == "You have already voted."


# --- Rate limiting -> 429 ---


async def test_rate_limiting(client):
    for _ in range(10):
        await client.post("/api/vote", json={"contestant": "Thompson"})
    r = await client.post("/api/vote", json={"contestant": "Thompson"})
    assert r.status_code == 429
    assert r.json()["detail"] == "Rate limit exceeded. Try again later."


# --- Input too long -> 400 ---


async def test_input_too_long(client):
    r = await client.post("/api/vote", json={"contestant": "a" * 101})
    assert r.status_code == 400
    assert (
        r.json()["detail"]
        == "Input exceeds maximum length of 100 characters."
    )


# --- Missing field -> 422 ---


async def test_missing_field(client):
    r = await client.post("/api/vote", json={"name": "Thompson"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Missing required field: contestant."


# --- Null value -> 422 ---


async def test_null_value(client):
    r = await client.post("/api/vote", json={"contestant": None})
    assert r.status_code == 422
    assert r.json()["detail"] == "Contestant must be a string."


# --- Non-string type -> 422 ---


async def test_non_string_type(client):
    r = await client.post("/api/vote", json={"contestant": 42})
    assert r.status_code == 422
    assert r.json()["detail"] == "Contestant must be a string."


# --- SQL injection -> sanitized -> 404 ---


async def test_sql_injection(client):
    r = await client.post(
        "/api/vote", json={"contestant": "'; DROP TABLE votes;--"}
    )
    assert r.status_code == 404
    assert "droptablevotes" in r.json()["detail"]


# --- XSS attempt -> sanitized -> 404 ---


async def test_xss_attempt(client):
    r = await client.post(
        "/api/vote", json={"contestant": "<script>alert(1)</script>"}
    )
    assert r.status_code == 404
    assert "scriptalertscript" in r.json()["detail"]


# --- Missing User-Agent -> 422 ---


async def test_missing_user_agent(client):
    r = await client.post(
        "/api/vote",
        json={"contestant": "Thompson"},
        headers={"user-agent": ""},
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "Missing User-Agent header."


# --- Same contestant from different devices -> both succeed ---


async def test_different_devices_same_contestant(client):
    r1 = await client.post(
        "/api/vote",
        json={"contestant": "Thompson"},
        headers={"user-agent": "Device-A"},
    )
    assert r1.status_code == 200

    r2 = await client.post(
        "/api/vote",
        json={"contestant": "Thompson"},
        headers={"user-agent": "Device-B"},
    )
    assert r2.status_code == 200
