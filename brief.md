# AGT Voting System — Intent Brief

Build a simplified "America's Got Talent" voting system. Voters enter a contestant's last name and click submit. That's the entire UI — one input, one button, success/error feedback.

**Backend (FastAPI):** Single POST endpoint accepts a last name, normalizes it (trim, lowercase, strip special characters), and validates against a hardcoded contestant roster. Reject unknown names with a clear error. Enforce vote integrity: fingerprint each voter using a hash of IP + User-Agent, store votes in SQLite, reject duplicate votes from the same fingerprint. Return JSON success/error responses with appropriate HTTP status codes.

**Frontend (Next.js App Router + Tailwind + MUI):** Minimal page with one MUI TextField, one MUI Button, and a feedback area showing success or error messages. No routing, no dashboards, no leaderboards.

**Integrity constraints:** One vote per device fingerprint. Normalize input before comparison. Sanitize all inputs. Rate-limit the vote endpoint to prevent abuse.

**What NOT to build:** Admin panels, analytics, WebSocket updates, leaderboards, user accounts, contestant management. The roster is hardcoded. The scope is intentionally small — ship it tight.