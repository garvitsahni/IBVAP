# SIH26187 — CCTV Video Analytics Console (Frontend, Phase 1)

Phase 1 scaffold: project setup, the ops-console shell (sidebar + topbar),
shared UI components, a mock officer-login auth flow, and routing for every
planned screen. Dashboard/Alerts/Cameras/History/Analytics are placeholder
screens for now — later phases fill them in with real functionality.

## Setup

```bash
npm install
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173). You'll be
redirected to `/login` — **any officer ID and password work** (mock auth).

## What's included

- **Routing** — `src/App.jsx`. Everything except `/login` is protected and
  redirects back to login if you're not "authenticated".
- **Auth (mocked)** — `src/context/AuthContext.jsx` fakes login with a short
  delay and persists the session to `localStorage`.
- **Console shell** — `src/components/layout/ConsoleLayout.jsx` wraps every
  authenticated page with `Sidebar` + `Topbar` (officer name, live clock).
- **Shared UI** — `src/components/ui/`: `Button`, `Card`, `Input`, `Spinner`,
  `Modal`, and `StatusBadge` (the critical/medium/low severity pill used for
  alerts from Phase 4 onward).
- **API client stub** — `src/api/client.js`, pre-wired for a future backend
  at `VITE_API_URL` (defaults to `http://localhost:5000/api`).

## Phase roadmap

1. **Foundation** — this phase.
2. **Officer login** — already included here to make the protected-route
   flow demoable; will get real validation/error handling.
3. **Live monitoring dashboard** — real camera feed grid + live alert stream.
4. **Alert / event detail view** — click-through detail panel, ANPR result,
   officer actions (acknowledge/escalate/false positive).
5. **Event history & analytics** — searchable log + basic charts.
6. **Polish** — simulated real-time alerts, responsive pass, empty/error states.

## Moving to a real backend

`AuthContext`'s `login()` currently fakes a response. Swap it for
`apiClient.post('/auth/login', { officerId, password })` once the backend
exists — the rest of the app only depends on the `{ officer, token }` shape
already returned, so nothing else needs to change.

## Design tokens

Colors, fonts, and spacing are CSS variables in `src/index.css` — a dark
tactical theme (slate background, tactical blue accent, red/amber/green
severity colors) chosen for a control-room environment.
