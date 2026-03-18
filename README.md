# AGT Voting System

A single-vote casting system for 10 contestants. One vote per device, rate-limited to 10 requests/minute per IP.

## Quick Start (< 5 minutes)

### Option A: Docker

```bash
docker compose up --build
```

Frontend: http://localhost:3000 | Backend: http://localhost:8000

### Option B: Local Development

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --workers 1
```

**Frontend** (new terminal):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Running Tests

**Backend:**

```bash
pip install httpx pytest pytest-asyncio
python -m pytest tests/test_backend.py -v
```

**Frontend:**

```bash
cd frontend
npm test
```

## Constraints

- Backend must run with `--workers 1` (in-memory rate limiter is not shared across processes).
- Valid contestants: Chen, Jensen, Kowalski, Martinez, Nakamura, Okafor, Patel, Rodriguez, Thompson, Williams.
