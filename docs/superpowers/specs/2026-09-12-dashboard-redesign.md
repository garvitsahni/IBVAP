# IBVAP Dashboard Redesign — BorderEye Integration

**Date:** 2026-09-12
**Status:** Approved
**Goal:** Replace the current IBVAP dashboard with the BorderEye visual design, upgraded to our stack, fully wired to our real backend, with Magic UI + framer-motion animations.

---

## 1. Source Material

### From BorderEye (adi-tya9919/sih26187-cctv-analytics-2)

**Keep:**
- `ConsoleLayout` (Sidebar + TopBar shell)
- `Sidebar` (nav with brand, links, officer profile, logout)
- `TopBar` (search, notification bell, live clock)
- `LoginPage` (hero image split layout)
- `AlertDetailPanel` (slide-out drawer with metadata, ANPR, actions)
- `AlertFeed` + `AlertItem` (vertical alert list with severity borders)
- `EventHistory` page (filterable table + stats sidebar)
- `EventTable` + `EventFilters` (sortable, searchable)
- `MapView` (Leaflet with camera markers, border zones)
- `Settings` page (officer profile, toggles)
- `StatsPanel` (event stats + bar chart)
- `ToastStack` (auto-dismissing notifications)
- `ConnectionStatus` (live/reconnecting indicator)
- `Skeletons` (loading placeholders)
- `EmptyState` (reusable empty/error)
- `ANPRDetails` (plate recognition display)
- `LocationIndicator` (map pin with coordinates)
- All UI primitives: `Button`, `Card`, `Input`, `Modal`, `Spinner`, `StatusBadge`, `StatCard`

**Remove:**
- `Login.jsx` (unused duplicate)
- `Dashboard.jsx` (unused duplicate)
- `mockData.js` (all mock data)
- `useAlertStream.js` (mock alert stream)
- `AuthContext.jsx` (mock auth)
- All `.css` component files (replaced by Tailwind v4)
- `api/client.js` (replaced by our API service)

### From Current IBVAP Dashboard

**Keep:**
- `DetectionOverlay` (bounding boxes with SSE + prop-based dual mode)
- `CameraGrid` (responsive grid with live feeds)
- `WebcamFeed` (exposure boost, frame capture, detection)
- `CameraFeed` (HLS streaming from backend)
- `CameraManager` (CRUD modal)
- `SSEClient` (real EventSource connection)
- `api.ts` (all real FastAPI endpoint calls)
- `sse.ts` (SSE event handling)
- TypeScript types (`api.ts` types)

---

## 2. Tech Stack

| Layer | Current | Target |
|-------|---------|--------|
| React | 18.3 | 19.x |
| Build | Vite 5.4 | Vite 8.x |
| CSS | Tailwind 3.4 + CSS files | Tailwind 4.x (CSS-first config) |
| Animations | None | Magic UI + framer-motion |
| Icons | lucide-react 0.468 | lucide-react (latest) |
| Maps | leaflet + react-leaflet | leaflet + react-leaflet (keep) |
| HTTP | axios | fetch (via our api.ts) |
| Router | react-router-dom 6.x | react-router-dom 7.x |

---

## 3. Architecture

```
dashboard/
├── index.html
├── package.json
├── vite.config.ts              # base: '/dashboard/', proxy /api → localhost:8000
├── src/
│   ├── main.tsx
│   ├── App.tsx                 # Routes + auth guard
│   ├── index.css               # Tailwind v4 CSS-first config + design tokens
│   ├── lib/
│   │   └── utils.ts            # cn() helper
│   ├── types/
│   │   └── api.ts              # All TypeScript interfaces (from current dashboard)
│   ├── services/
│   │   ├── api.ts              # FastAPI client (from current dashboard)
│   │   └── sse.ts              # SSE client (from current dashboard)
│   ├── hooks/
│   │   ├── useAlertStream.ts   # Real SSE alert stream
│   │   └── useCameraHealth.ts  # Camera health polling
│   ├── components/
│   │   ├── layout/
│   │   │   ├── ConsoleLayout.tsx    # Sidebar + TopBar shell
│   │   │   ├── Sidebar.tsx          # Animated sidebar (Magic UI)
│   │   │   └── TopBar.tsx           # Live clock, search, notifications
│   │   ├── ui/                      # All UI primitives (Button, Card, etc.)
│   │   ├── alert/
│   │   │   ├── AlertFeed.tsx        # AnimatedList for alerts
│   │   │   ├── AlertItem.tsx        # Severity border + BorderBeam
│   │   │   ├── AlertDetailPanel.tsx # Slide-out drawer
│   │   │   └── ToastStack.tsx       # Animated toasts
│   │   ├── camera/
│   │   │   ├── CameraGrid.tsx       # Responsive camera tile grid
│   │   │   ├── CameraTile.tsx       # Individual feed + BorderBeam
│   │   │   ├── CameraFeed.tsx       # HLS stream + detection overlay
│   │   │   ├── WebcamFeed.tsx       # Browser cam + exposure boost
│   │   │   ├── DetectionOverlay.tsx # Bounding boxes
│   │   │   └── CameraManager.tsx    # CRUD modal
│   │   ├── event/
│   │   │   ├── EventTable.tsx       # Sortable table
│   │   │   └── EventFilters.tsx     # Search + filters
│   │   ├── map/
│   │   │   └── MapView.tsx          # Leaflet map
│   │   └── stats/
│   │       ├── StatsPanel.tsx       # NumberTicker for counts
│   │       └── BarChart.tsx         # Pure-div chart
│   └── pages/
│       ├── LoginPage.tsx
│       ├── DashboardPage.tsx        # Main live monitoring
│       ├── AlertsPage.tsx
│       ├── EventHistoryPage.tsx
│       ├── MapPage.tsx
│       └── SettingsPage.tsx
```

---

## 4. Design Tokens (Unified Dark Theme)

All styling uses Tailwind v4 CSS-first config. No separate `.css` files.

```css
@theme {
  --color-bg: #0a0e14;
  --color-surface: #111820;
  --color-surface-2: #1a2230;
  --color-surface-3: #222d3d;
  --color-border: #1e2a3a;
  --color-border-light: #2a3a4e;

  --color-text: #e8edf4;
  --color-text-secondary: #8899aa;
  --color-text-muted: #556677;

  --color-accent: #3da5d9;
  --color-accent-hover: #5bb8e8;

  --color-severity-critical: #ef4444;
  --color-severity-high: #f97316;
  --color-severity-medium: #eab308;
  --color-severity-low: #22c55e;
  --color-severity-info: #3b82f6;

  --color-status-online: #22c55e;
  --color-status-offline: #ef4444;
  --color-status-degraded: #eab308;
}
```

---

## 5. Animation Specifications

### Magic UI Components

| Component | Placement | Config |
|-----------|-----------|--------|
| `BorderBeam` | CameraTile (online), AlertItem (critical), active nav item | `duration={6}`, color matches severity |
| `AnimatedList` | AlertFeed | Stagger delay 100ms per item |
| `NumberTicker` | StatsPanel counters | `duration={2000}`, spring transition |
| `ShimmerButton` | Action buttons (Acknowledge, Escalate, False Positive) | Default shimmer |
| `PulsatingButton` | "Live" indicator in TopBar | `duration={2000}` pulse |
| `DotPattern` | LoginPage background, EmptyState | `cellSize={20}`, low opacity |
| `AnimatedGradientText` | "IBVAP" brand in Sidebar | `colors={["#3da5d9", "#22c55e", "#3da5d9"]}` |
| `Marquee` | Alert ticker in TopBar (optional) | Speed 30, pause on hover |

### Framer Motion

| Effect | Target | Config |
|--------|--------|--------|
| Page transitions | All routes via `AnimatePresence` | `fade` 200ms |
| Stagger children | CameraGrid, EventTable, AlertFeed | `staggerChildren: 0.05` |
| Hover scale | Cards, nav items, buttons | `scale: 1.02` on hover |
| Layout animation | AlertDetailPanel slide-out | `spring` transition |
| Exit animation | Toast notifications, modals | `opacity: 0, y: 20` exit |

### Implementation Pattern

```tsx
// Example: Animated camera tile
import { BorderBeam } from "@/registry/magicui/border-beam";
import { motion } from "framer-motion";

<motion.div
  whileHover={{ scale: 1.02 }}
  transition={{ type: "spring", stiffness: 300 }}
  className="relative"
>
  <CameraFeed ... />
  {isOnline && (
    <BorderBeam
      duration={6}
      size={200}
      className="from-transparent via-status-online to-transparent"
    />
  )}
</motion.div>
```

---

## 6. Backend Wiring

All API calls route through our existing `api.ts` service. The proxy in `vite.config.ts` forwards `/api` to `http://localhost:8000`.

| Feature | Backend Endpoint | Method |
|---------|-----------------|--------|
| Camera list | `GET /api/v1/cameras` | REST |
| Camera CRUD | `POST/PUT/DELETE /api/v1/cameras/{id}` | REST |
| Camera health | `GET /api/v1/cameras/{id}/health` | REST |
| Camera seed | `POST /api/v1/cameras/seed-local` | REST |
| Detection | `POST /api/v1/detect` | REST |
| Alert stream | `GET /api/v1/alerts/stream` | SSE |
| Detection events | `GET /api/v1/detections` | REST |
| Event history | `GET /api/v1/events` | REST |
| Ledger status | `GET /api/v1/ledger/status` | REST |
| Footprint chain | `GET /api/v1/footprint/{object_id}` | REST |

### SSE Events

| Event | Source | Handler |
|-------|--------|---------|
| `alert` | Alert pipeline | Update AlertFeed, trigger Toast |
| `detection` | Event creation | Update DetectionOverlay |
| `camera_health` | Health monitor | Update camera status dots |

---

## 7. Pages

### LoginPage (`/login`)
- Split layout: hero image left, form right
- DotPattern background
- AnimatedGradientText for "IBVAP" branding
- Real auth against backend (JWT)

### DashboardPage (`/dashboard`)
- ConsoleLayout shell (Sidebar + TopBar)
- CameraGrid (left ~70%) + AlertFeed (right ~30%)
- Click alert → AlertDetailPanel slide-out
- ToastStack for new alerts
- ConnectionStatus in TopBar

### AlertsPage (`/alerts`)
- Full alert list with AlertDetailPanel
- Filter by severity, camera, time range

### EventHistoryPage (`/history`)
- EventTable + EventFilters
- StatsPanel sidebar with NumberTicker

### MapPage (`/map`)
- Leaflet map with camera markers
- Border zone polygons
- Camera status colored markers

### SettingsPage (`/settings`)
- Officer profile
- Notification toggles

---

## 8. Migration Strategy

1. Clone BorderEye repo to `dashboard-new/`
2. Upgrade deps (React 19, Vite 8, Tailwind v4)
3. Delete all mock data, .css files, duplicate pages
4. Port our TypeScript types, API service, SSE client
5. Rewrite components to use real API calls
6. Port DetectionOverlay, CameraFeed, WebcamFeed, CameraManager
7. Add Magic UI + framer-motion animations
8. Unify theme (one dark theme, all tokens in Tailwind v4)
9. Test all pages against running backend
10. Replace old `dashboard/` with new code
11. Rebuild, verify 394 Python tests still pass
12. Push to GitHub

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Magic UI requires shadcn/ui base | Install shadcn/ui first, then add Magic UI components |
| Tailwind v4 migration breaks classes | Run `@tailwindcss/upgrade` tool, manual fixup |
| Framer Motion bundle size | Tree-shake, only import used animations |
| Login image is 1.5MB | Compress to <200KB or use CSS gradient |
| No error boundaries | Add React error boundary around Router |
