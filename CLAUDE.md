# AGT Voting System

## Tech Stack
- Frontend: Next.js (App Router), Tailwind CSS, MUI
- Backend: Python / FastAPI
- Testing: pytest (backend), Jest + React Testing Library (frontend)

## Constraints
- NO unrequested features (no dashboards, leaderboards, admin panels, WebSocket updates, analytics)
- Build EXACTLY what is specified — no more
- Input sanitization and security hardening ARE expected
- Vote integrity: prevent duplicate votes, prevent casual fraud
- Single text input + submit button on frontend
- Success/error feedback only

## Workflow
- Atomic git commits after every meaningful change
- Tests written alongside code, not after
- Code → test → fix → re-test loop until green