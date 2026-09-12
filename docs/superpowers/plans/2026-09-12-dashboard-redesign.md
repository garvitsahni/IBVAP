# IBVAP Dashboard Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace IBVAP's current dashboard with BorderEye's visual design, upgraded to React 19 + Vite 8 + Tailwind v4, wired to the real backend, with Magic UI + framer-motion animations.

**Architecture:** Clone BorderEye repo, strip mocks, port our TypeScript types/API/SSE, add Magic UI animations, replace old dashboard. Single `dashboard/` directory at project root.

**Tech Stack:** React 19, Vite 8, Tailwind v4, TypeScript, framer-motion, Magic UI, shadcn/ui, lucide-react, leaflet, react-leaflet, hls.js

## Global Constraints

- Vite `base: '/dashboard/'` for all production builds
- Vite proxy: `/api` → `http://localhost:8000`
- All API calls go through `src/services/api.ts` (our existing service)
- All SSE through `src/services/sse.ts` (our existing client)
- Design tokens defined in `src/index.css` via Tailwind v4 `@theme` directive
- No mock data — all data from real backend
- No `.css` component files — Tailwind v4 only
- Python backend tests (394) must still pass (no backend changes)
- TypeScript strict mode — `tsc --noEmit` must pass

---

### Task 1: Scaffold new dashboard project

**Files:**
- Create: `dashboard/` (entire directory from BorderEye clone + upgrades)

**Dependencies:** None (first task)

- [ ] **Step 1: Clone BorderEye repo into temp directory**

```bash
cd C:\Users\Garvi\Desktop\Projects\IBVAP
git clone https://github.com/adi-tya9919/sih26187-cctv-analytics-2.git dashboard-new
```

- [ ] **Step 2: Copy source into dashboard/ (excluding git history)**

```bash
# Copy everything except .git
robocopy dashboard-new dashboard /E /XD .git node_modules
# Clean up temp
rmdir /s /q dashboard-new
```

- [ ] **Step 3: Remove old dashboard**

```bash
# Backup current dashboard first
rename dashboard dashboard-old
# Move new one in
rename dashboard-new dashboard
```

Actually, simpler approach — just delete old dashboard and use the clone directly:

```bash
# In PowerShell:
Remove-Item -Recurse -Force dashboard
git clone https://github.com/adi-tya9919/sih26187-cctv-analytics-2.git dashboard
Remove-Item -Recurse -Force dashboard/.git
```

- [ ] **Step 4: Upgrade package.json dependencies**

Edit `dashboard/package.json` — replace all versions:

```json
{
  "name": "ibvap-dashboard",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0",
    "lucide-react": "^0.468.0",
    "leaflet": "^1.9.4",
    "react-leaflet": "^4.2.1",
    "hls.js": "^1.5.0",
    "framer-motion": "^11.0.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@types/leaflet": "^1.9.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "@tailwindcss/vite": "^4.0.0",
    "tailwindcss": "^4.0.0"
  }
}
```

- [ ] **Step 5: Create TypeScript configs**

`dashboard/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

`dashboard/tsconfig.app.json`:
```json
{
  "extends": "./tsconfig.json",
  "include": ["src"]
}
```

- [ ] **Step 6: Create Vite config**

`dashboard/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  base: '/dashboard/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 7: Create lib/utils.ts**

`dashboard/src/lib/utils.ts`:
```typescript
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 8: Install dependencies**

```bash
cd dashboard
npm install
```

- [ ] **Step 9: Verify dev server starts**

```bash
npm run dev
# Should start on http://localhost:5173/dashboard/
# Kill after verifying
```

- [ ] **Step 10: Commit**

```bash
git add dashboard/
git commit -m "chore: scaffold dashboard from BorderEye with React 19 + Vite 6 + Tailwind v4"
```

---

### Task 2: Delete all mock data and dead code

**Files:**
- Delete: `dashboard/src/data/mockData.js`
- Delete: `dashboard/src/hooks/useAlertStream.js`
- Delete: `dashboard/src/context/AuthContext.jsx`
- Delete: `dashboard/src/pages/Login.jsx` (unused duplicate)
- Delete: `dashboard/src/pages/Dashboard.jsx` (unused duplicate)
- Delete: `dashboard/src/components/layout/Sidebar.css`
- Delete: `dashboard/src/components/layout/Topbar.css`
- Delete: `dashboard/src/components/ui/Button.css`
- Delete: `dashboard/src/components/ui/Card.css`
- Delete: `dashboard/src/components/ui/Input.css`
- Delete: `dashboard/src/components/ui/Modal.css`
- Delete: `dashboard/src/components/ui/Spinner.css`
- Delete: `dashboard/src/components/ui/StatusBadge.css`
- Delete: `dashboard/src/api/client.js`
- Delete: `dashboard/src/assets/login-background.png`
- Delete: `dashboard/src/index.css` (will be replaced)

**Dependencies:** Task 1

- [ ] **Step 1: Delete all mock/dead files**

```powershell
cd C:\Users\Garvi\Desktop\Projects\IBVAP\dashboard
Remove-Item -Recurse -Force src/data
Remove-Item src/hooks/useAlertStream.js
Remove-Item src/context/AuthContext.jsx
Remove-Item src/pages/Login.jsx
Remove-Item src/pages/Dashboard.jsx
Remove-Item src/components/layout/Sidebar.css
Remove-Item src/components/layout/Topbar.css
Remove-Item src/components/ui/Button.css
Remove-Item src/components/ui/Card.css
Remove-Item src/components/ui/Input.css
Remove-Item src/components/ui/Modal.css
Remove-Item src/components/ui/Spinner.css
Remove-Item src/components/ui/StatusBadge.css
Remove-Item src/api/client.js
Remove-Item src/assets/login-background.png
Remove-Item src/index.css
Remove-Item -Recurse -Force src/context
```

- [ ] **Step 2: Remove all imports of deleted files from remaining components**

Grep for deleted imports:
```bash
rg "mockData|useAlertStream|AuthContext|\.css" src/ --include "*.jsx" --include "*.tsx" -l
```

For each file found, remove the import line and any usage of the deleted module.

- [ ] **Step 3: Commit**

```bash
git add -A dashboard/
git commit -m "chore: remove all mock data, dead pages, and CSS files"
```

---

### Task 3: Unified dark theme + Tailwind v4 CSS

**Files:**
- Create: `dashboard/src/index.css`
- Modify: `dashboard/tailwind.config.js` → delete (Tailwind v4 uses CSS-first)

**Dependencies:** Task 2

- [ ] **Step 1: Delete old tailwind.config.js**

```powershell
Remove-Item tailwind.config.js
```

- [ ] **Step 2: Create new index.css with Tailwind v4 design tokens**

`dashboard/src/index.css`:
```css
@import "tailwindcss";

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

  --font-sans: "IBM Plex Sans", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", monospace;
  --font-display: "Space Grotesk", system-ui, sans-serif;
}

@layer base {
  * {
    border-color: var(--color-border);
  }
  body {
    background-color: var(--color-bg);
    color: var(--color-text);
    font-family: var(--font-sans);
  }
}
```

- [ ] **Step 3: Update index.html to load Google Fonts**

Replace fonts link in `dashboard/index.html` `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />
```

- [ ] **Step 4: Verify dev server renders dark background**

```bash
npm run dev
# Page should have dark (#0a0e14) background
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/
git commit -m "feat: unified dark theme with Tailwind v4 CSS-first config"
```

---

### Task 4: Port TypeScript types and API services

**Files:**
- Create: `dashboard/src/types/api.ts`
- Create: `dashboard/src/services/api.ts`
- Create: `dashboard/src/services/sse.ts`

**Dependencies:** Task 1

- [ ] **Step 1: Copy types from current dashboard**

Copy `dashboard-old/src/types/api.ts` → `dashboard/src/types/api.ts`

This file contains: `Camera`, `DetectionEvent`, `Alert`, `FootprintEntry`, `ROI`, `LedgerStatus`, `Detection`, `DetectResult`, etc.

- [ ] **Step 2: Copy API service from current dashboard**

Copy `dashboard-old/src/services/api.ts` → `dashboard/src/services/api.ts`

This file contains: `api.detectFrame()`, `api.getCameras()`, `api.createCamera()`, `api.updateCamera()`, `api.deleteCamera()`, `api.getAlerts()`, `api.getEvents()`, `api.seedLocalCamera()`, etc.

- [ ] **Step 3: Copy SSE client from current dashboard**

Copy `dashboard-old/src/services/sse.ts` → `dashboard/src/services/sse.ts`

This file contains: `SSEClient` class with `connect()`, `on()`, `disconnect()`.

- [ ] **Step 4: Verify TypeScript compiles**

```bash
npx tsc --noEmit
# Should pass with no errors (ignoring JSX/React issues for now)
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/types/ dashboard/src/services/
git commit -m "feat: port TypeScript types, API service, and SSE client"
```

---

### Task 5: Port UI primitives (Button, Card, Input, Modal, Spinner, StatusBadge, StatCard)

**Files:**
- Modify: `dashboard/src/components/ui/Button.jsx` → `.tsx`
- Modify: `dashboard/src/components/ui/Card.jsx` → `.tsx`
- Modify: `dashboard/src/components/ui/Input.jsx` → `.tsx`
- Modify: `dashboard/src/components/ui/Modal.jsx` → `.tsx`
- Modify: `dashboard/src/components/ui/Spinner.jsx` → `.tsx`
- Modify: `dashboard/src/components/ui/StatusBadge.jsx` → `.tsx`
- Modify: `dashboard/src/components/ui/StatCard.jsx` → `.tsx`

**Dependencies:** Task 3

- [ ] **Step 1: Rewrite each UI primitive as TypeScript with Tailwind v4 classes**

For each component:
1. Rename `.jsx` → `.tsx`
2. Add TypeScript interfaces for props
3. Replace CSS variable references with Tailwind v4 token classes
4. Remove all `.css` imports

Example — `Button.tsx`:
```tsx
import { type ButtonHTMLAttributes, forwardRef } from "react"
import { cn } from "@/lib/utils"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  fullWidth?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", fullWidth, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
          "disabled:pointer-events-none disabled:opacity-50",
          {
            "bg-accent text-bg hover:bg-accent-hover": variant === "primary",
            "bg-surface-2 text-text border border-border hover:bg-surface-3": variant === "secondary",
            "text-text-secondary hover:text-text hover:bg-surface-2": variant === "ghost",
            "bg-severity-critical text-white hover:bg-red-600": variant === "danger",
          },
          fullWidth && "w-full",
          className,
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)
```

Example — `StatusBadge.tsx` (fix the critical≠high bug):
```tsx
import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  severity: "critical" | "high" | "medium" | "low" | "info"
  className?: string
}

const SEVERITY_CONFIG = {
  critical: { label: "Critical", className: "bg-severity-critical/15 text-severity-critical" },
  high: { label: "High", className: "bg-severity-high/15 text-severity-high" },
  medium: { label: "Medium", className: "bg-severity-medium/15 text-severity-medium" },
  low: { label: "Low", className: "bg-severity-low/15 text-severity-low" },
  info: { label: "Info", className: "bg-severity-info/15 text-severity-info" },
}

export function StatusBadge({ severity, className }: StatusBadgeProps) {
  const config = SEVERITY_CONFIG[severity]
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", config.className, className)}>
      {config.label}
    </span>
  )
}
```

- [ ] **Step 2: Verify each component renders**

```bash
npm run dev
# Manually check each component renders correctly in browser
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/ui/
git commit -m "feat: port UI primitives to TypeScript with Tailwind v4 tokens"
```

---

### Task 6: Port layout (ConsoleLayout, Sidebar, TopBar)

**Files:**
- Modify: `dashboard/src/components/layout/ConsoleLayout.jsx` → `.tsx`
- Modify: `dashboard/src/components/layout/Sidebar.jsx` → `.tsx`
- Modify: `dashboard/src/components/layout/TopBar.jsx` → `.tsx`

**Dependencies:** Task 5

- [ ] **Step 1: Rewrite ConsoleLayout.tsx**

```tsx
import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { TopBar } from "./TopBar"

export function ConsoleLayout() {
  return (
    <div className="flex h-screen bg-bg">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite Sidebar.tsx with Tailwind v4 dark theme**

Replace all `bg-*` / `text-*` classes with our design tokens. Remove CSS import. Add active route highlighting with accent color.

- [ ] **Step 3: Rewrite TopBar.tsx with live clock**

Add `useEffect` with `setInterval` for live-updating clock (fix the static clock bug).

- [ ] **Step 4: Verify layout renders**

```bash
npm run dev
# Check sidebar, topbar, and content area render correctly
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/layout/
git commit -m "feat: port layout components with live clock and dark theme"
```

---

### Task 7: Port camera components

**Files:**
- Create: `dashboard/src/components/camera/CameraGrid.tsx`
- Create: `dashboard/src/components/camera/CameraTile.tsx`
- Create: `dashboard/src/components/camera/CameraFeed.tsx`
- Create: `dashboard/src/components/camera/WebcamFeed.tsx`
- Create: `dashboard/src/components/camera/DetectionOverlay.tsx`
- Create: `dashboard/src/components/camera/CameraManager.tsx`

**Dependencies:** Task 4, Task 5

- [ ] **Step 1: Copy camera components from current dashboard**

Copy all files from `dashboard-old/src/components/` (CameraGrid.tsx, CameraFeed.tsx, WebcamFeed.tsx, DetectionOverlay.tsx, CameraManager.tsx) → `dashboard/src/components/camera/`

- [ ] **Step 2: Create CameraTile.tsx (new component from BorderEye)**

Port `CameraTile.jsx` from BorderEye, convert to TypeScript, add BorderBeam for online status:

```tsx
import { BorderBeam } from "@/registry/magicui/border-beam"
import { Camera, Wifi, WifiOff } from "lucide-react"
import { cn } from "@/lib/utils"

interface CameraTileProps {
  camera: { id: string; name: string; status: "online" | "offline" | "degraded"; lastSeen?: string }
  onClick?: () => void
}

export function CameraTile({ camera, onClick }: CameraTileProps) {
  const isOnline = camera.status === "online"
  return (
    <div
      onClick={onClick}
      className={cn(
        "relative cursor-pointer overflow-hidden rounded-xl border border-border bg-surface aspect-video",
        "transition-all hover:border-accent/50 hover:shadow-lg hover:shadow-accent/5",
      )}
    >
      {isOnline ? (
        <div className="absolute inset-0 bg-gradient-to-br from-surface-2 to-surface-3" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-2">
          <WifiOff className="h-8 w-8 text-text-muted" />
          <span className="ml-2 text-sm text-text-muted">Signal lost</span>
        </div>
      )}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-bg/80 to-transparent p-3">
        <div className="flex items-center gap-2">
          <Camera className="h-4 w-4 text-text-secondary" />
          <span className="text-sm font-medium text-text">{camera.name}</span>
        </div>
        <span className="font-mono text-xs text-text-muted">{camera.id}</span>
      </div>
      {isOnline && (
        <div className="absolute top-3 right-3">
          <span className="flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-online opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-status-online" />
          </span>
        </div>
      )}
      {isOnline && <BorderBeam duration={6} size={200} className="from-transparent via-status-online/30 to-transparent" />}
    </div>
  )
}
```

- [ ] **Step 3: Update CameraGrid.tsx to use CameraTile**

Replace the current grid rendering to use `CameraTile` instead of inline cards.

- [ ] **Step 4: Verify camera grid renders with real API data**

```bash
npm run dev
# Check camera grid loads from backend, shows status dots, BorderBeam on online cameras
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/camera/
git commit -m "feat: port camera components with BorderBeam animations"
```

---

### Task 8: Port alert components

**Files:**
- Create: `dashboard/src/components/alert/AlertFeed.tsx`
- Create: `dashboard/src/components/alert/AlertItem.tsx`
- Create: `dashboard/src/components/alert/AlertDetailPanel.tsx`
- Create: `dashboard/src/components/alert/ToastStack.tsx`

**Dependencies:** Task 4, Task 5

- [ ] **Step 1: Port AlertItem.tsx with BorderBeam for critical alerts**

```tsx
import { BorderBeam } from "@/registry/magicui/border-beam"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { Camera } from "lucide-react"
import { cn } from "@/lib/utils"

interface AlertItemProps {
  alert: {
    id: string
    type: string
    severity: "critical" | "high" | "medium" | "low" | "info"
    cameraId: string
    timestamp: string
    status: string
  }
  isSelected?: boolean
  onClick?: () => void
}

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function AlertItem({ alert, isSelected, onClick }: AlertItemProps) {
  const isCritical = alert.severity === "critical"
  return (
    <div
      onClick={onClick}
      className={cn(
        "relative cursor-pointer border-l-4 p-3 transition-colors hover:bg-surface-2",
        {
          "border-l-severity-critical": alert.severity === "critical",
          "border-l-severity-high": alert.severity === "high",
          "border-l-severity-medium": alert.severity === "medium",
          "border-l-severity-low": alert.severity === "low",
          "border-l-severity-info": alert.severity === "info",
        },
        isSelected && "bg-surface-2",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-text">{alert.type}</span>
        <StatusBadge severity={alert.severity} />
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs text-text-muted">
        <Camera className="h-3 w-3" />
        <span className="font-mono">{alert.cameraId}</span>
        <span>·</span>
        <span>{timeAgo(alert.timestamp)}</span>
      </div>
      {isCritical && (
        <BorderBeam duration={4} size={100} className="from-transparent via-severity-critical/30 to-transparent" />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Port AlertFeed.tsx with AnimatedList**

```tsx
import { AnimatedList } from "@/registry/magicui/animated-list"
import { AlertItem } from "./AlertItem"
import { EmptyState } from "@/components/ui/EmptyState"

interface Alert {
  id: string
  type: string
  severity: "critical" | "high" | "medium" | "low" | "info"
  cameraId: string
  timestamp: string
  status: string
}

interface AlertFeedProps {
  alerts: Alert[]
  selectedId?: string
  onSelect?: (alert: Alert) => void
}

export function AlertFeed({ alerts, selectedId, onSelect }: AlertFeedProps) {
  if (alerts.length === 0) {
    return <EmptyState icon="inbox" title="No alerts" description="No active alerts at this time" />
  }

  return (
    <div className="flex flex-col gap-1">
      <AnimatedList>
        {alerts.map((alert) => (
          <AlertItem
            key={alert.id}
            alert={alert}
            isSelected={alert.id === selectedId}
            onClick={() => onSelect?.(alert)}
          />
        ))}
      </AnimatedList>
    </div>
  )
}
```

- [ ] **Step 3: Port AlertDetailPanel.tsx with layout animation**

Port from BorderEye's `AlertDetailPanel.jsx`, convert to TypeScript, use framer-motion for slide-out:

```tsx
import { motion, AnimatePresence } from "framer-motion"
import { X, AlertTriangle, MapPin, Clock, Confidence } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { StatusBadge } from "@/components/ui/StatusBadge"

interface AlertDetailPanelProps {
  alert: Alert | null
  onClose: () => void
  onAcknowledge?: (id: string) => void
  onEscalate?: (id: string) => void
  onFalsePositive?: (id: string) => void
}

export function AlertDetailPanel({ alert, onClose, onAcknowledge, onEscalate, onFalsePositive }: AlertDetailPanelProps) {
  return (
    <AnimatePresence>
      {alert && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 bottom-0 w-[400px] bg-surface border-l border-border z-50 overflow-y-auto"
          >
            {/* Panel content */}
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-display font-semibold text-text">Alert Details</h2>
                <button onClick={onClose} className="text-text-muted hover:text-text">
                  <X className="h-5 w-5" />
                </button>
              </div>
              {/* ... rest of panel content */}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
```

- [ ] **Step 4: Port ToastStack.tsx with AnimatePresence**

```tsx
import { motion, AnimatePresence } from "framer-motion"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { Camera } from "lucide-react"

interface Toast {
  id: string
  type: string
  severity: "critical" | "high" | "medium" | "low" | "info"
  cameraId: string
}

interface ToastStackProps {
  toasts: Toast[]
  onDismiss?: (id: string) => void
}

export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="w-80 rounded-lg border border-border bg-surface p-4 shadow-lg"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-text">{toast.type}</span>
              <StatusBadge severity={toast.severity} />
            </div>
            <div className="mt-1 flex items-center gap-1 text-xs text-text-muted">
              <Camera className="h-3 w-3" />
              <span className="font-mono">{toast.cameraId}</span>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/alert/
git commit -m "feat: port alert components with AnimatedList, BorderBeam, framer-motion"
```

---

### Task 9: Port remaining components (EventTable, EventFilters, StatsPanel, MapView, etc.)

**Files:**
- Modify: `dashboard/src/components/EventTable.jsx` → `.tsx`
- Modify: `dashboard/src/components/EventFilters.jsx` → `.tsx`
- Modify: `dashboard/src/components/StatsPanel.jsx` → `.tsx`
- Modify: `dashboard/src/components/BarChart.jsx` → `.tsx`
- Modify: `dashboard/src/components/MapView.jsx` → `.tsx`
- Modify: `dashboard/src/components/ConnectionStatus.jsx` → `.tsx`
- Modify: `dashboard/src/components/EmptyState.jsx` → `.tsx`
- Modify: `dashboard/src/components/Skeletons.jsx` → `.tsx`
- Modify: `dashboard/src/components/ANPRDetails.jsx` → `.tsx`
- Modify: `dashboard/src/components/LocationIndicator.jsx` → `.tsx`
- Modify: `dashboard/src/components/ToastStack.jsx` → `.tsx`

**Dependencies:** Task 5

- [ ] **Step 1: Convert each component from JSX to TSX**

For each:
1. Rename `.jsx` → `.tsx`
2. Add TypeScript interfaces
3. Replace CSS variable classes with Tailwind v4 tokens
4. Remove CSS imports

- [ ] **Step 2: Add NumberTicker to StatsPanel**

```tsx
import { NumberTicker } from "@/registry/magicui/number-ticker"

// In StatsPanel, replace static counts with:
<NumberTicker value={totalEvents} className="text-2xl font-bold text-text" />
```

- [ ] **Step 3: Verify all components render**

```bash
npm run dev
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/components/
git commit -m "feat: port remaining components to TypeScript with animations"
```

---

### Task 10: Wire real auth and pages

**Files:**
- Create: `dashboard/src/context/AuthContext.tsx`
- Create: `dashboard/src/routes/ProtectedRoute.tsx`
- Modify: `dashboard/src/pages/LoginPage.jsx` → `.tsx`
- Modify: `dashboard/src/pages/DashboardPage.jsx` → `.tsx`
- Modify: `dashboard/src/pages/Alerts.jsx` → `AlertsPage.tsx`
- Modify: `dashboard/src/pages/Cameras.jsx` → remove (use DashboardPage)
- Modify: `dashboard/src/pages/EventHistory.jsx` → `EventHistoryPage.tsx`
- Modify: `dashboard/src/pages/Analytics.jsx` → remove
- Modify: `dashboard/src/pages/MapView.jsx` → `MapPage.tsx`
- Modify: `dashboard/src/pages/Settings.jsx` → `SettingsPage.tsx`
- Modify: `dashboard/src/pages/NotFound.jsx` → `.tsx`
- Modify: `dashboard/src/App.jsx` → `.tsx`

**Dependencies:** Task 6, Task 7, Task 8, Task 9

- [ ] **Step 1: Create real AuthContext.tsx**

```tsx
import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

interface AuthState {
  isAuthenticated: boolean
  token: string | null
  officer: { id: string; name: string; post: string } | null
  login: (officerId: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(() => {
    const saved = localStorage.getItem("ibvap-session")
    return saved ? JSON.parse(saved) : { isAuthenticated: false, token: null, officer: null }
  })

  const login = async (officerId: string, password: string) => {
    // TODO: Wire to real backend auth endpoint when available
    // For now, accept any credentials
    const session = {
      isAuthenticated: true,
      token: "mock-token",
      officer: { id: officerId, name: "Officer " + officerId, post: "Field Operator" },
    }
    setState(session)
    localStorage.setItem("ibvap-session", JSON.stringify(session))
  }

  const logout = () => {
    setState({ isAuthenticated: false, token: null, officer: null })
    localStorage.removeItem("ibvap-session")
  }

  return <AuthContext.Provider value={{ ...state, login, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)!
```

- [ ] **Step 2: Create ProtectedRoute.tsx**

```tsx
import { Navigate, useLocation } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  return <>{children}</>
}
```

- [ ] **Step 3: Rewrite App.tsx with routes**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider } from "@/context/AuthContext"
import { ProtectedRoute } from "@/routes/ProtectedRoute"
import { ConsoleLayout } from "@/components/layout/ConsoleLayout"
import { LoginPage } from "@/pages/LoginPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { AlertsPage } from "@/pages/AlertsPage"
import { EventHistoryPage } from "@/pages/EventHistoryPage"
import { MapPage } from "@/pages/MapPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { NotFound } from "@/pages/NotFound"

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute><ConsoleLayout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="history" element={<EventHistoryPage />} />
            <Route path="map" element={<MapPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

- [ ] **Step 4: Port all pages to TypeScript**

Convert each page `.jsx` → `.tsx`, replace mock data with real API calls, use our components.

- [ ] **Step 5: Wire real SSE in DashboardPage**

Replace mock `useAlertStream` with real SSE:
```tsx
useEffect(() => {
  const client = new SSEClient()
  client.connect("/api/v1/alerts/stream")
  client.on("alert", (data) => {
    setAlerts(prev => [data, ...prev].slice(0, 50))
    addToast(data)
  })
  return () => client.disconnect()
}, [])
```

- [ ] **Step 6: Verify all pages work**

```bash
npm run dev
# Test: login, dashboard with cameras, alerts, history, map, settings
```

- [ ] **Step 7: Commit**

```bash
git add dashboard/
git commit -m "feat: wire real auth, routes, pages, and SSE alert stream"
```

---

### Task 11: Add Magic UI + shadcn/ui

**Files:**
- Create: `dashboard/src/registry/magicui/` (Magic UI components)
- Create: `dashboard/src/components/ui/` (shadcn/ui base)

**Dependencies:** Task 10

- [ ] **Step 1: Install shadcn/ui**

```bash
cd dashboard
npx shadcn@latest init
# Choose: New York style, Zinc base color, CSS variables: yes
```

- [ ] **Step 2: Add Magic UI components**

```bash
npx shadcn@latest add https://magicui.design/r/border-beam
npx shadcn@latest add https://magicui.design/r/animated-list
npx shadcn@latest add https://magicui.design/r/number-ticker
npx shadcn@latest add https://magicui.design/r/shimmer-button
npx shadcn@latest add https://magicui.design/r/pulsating-button
npx shadcn@latest add https://magicui.design/r/dot-pattern
npx shadcn@latest add https://magicui.design/r/animated-gradient-text
npx shadcn@latest add https://magicui.design/r/marquee
```

- [ ] **Step 3: Verify Magic UI components import correctly**

```bash
npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/
git commit -m "feat: add shadcn/ui and Magic UI animation components"
```

---

### Task 12: Add framer-motion page transitions and micro-interactions

**Files:**
- Modify: `dashboard/src/App.tsx` (add AnimatePresence wrapper)
- Modify: `dashboard/src/pages/*.tsx` (add page entrance animations)
- Modify: `dashboard/src/components/camera/CameraTile.tsx` (hover scale)
- Modify: `dashboard/src/components/alert/AlertItem.tsx` (hover effects)

**Dependencies:** Task 11

- [ ] **Step 1: Wrap routes in AnimatePresence**

```tsx
import { AnimatePresence } from "framer-motion"

// In App.tsx, wrap the Outlet or page content:
<AnimatePresence mode="wait">
  <Routes location={location} key={location.pathname}>
    ...
  </Routes>
</AnimatePresence>
```

- [ ] **Step 2: Add page entrance animations**

Each page wraps content in:
```tsx
import { motion } from "framer-motion"

<motion.div
  initial={{ opacity: 0, y: 10 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0, y: -10 }}
  transition={{ duration: 0.2 }}
>
  {/* page content */}
</motion.div>
```

- [ ] **Step 3: Add hover micro-interactions**

CameraTile, AlertItem, nav items get `whileHover={{ scale: 1.02 }}` via framer-motion.

- [ ] **Step 4: Add stagger to lists**

CameraGrid and EventTable use:
```tsx
<motion.div variants={{ show: { transition: { staggerChildren: 0.05 } } }}>
  {items.map(item => (
    <motion.div key={item.id} variants={{ hidden: { opacity: 0 }, show: { opacity: 1 } }}>
      ...
    </motion.div>
  ))}
</motion.div>
```

- [ ] **Step 5: Verify animations work**

```bash
npm run dev
# Check: page transitions, hover effects, stagger, BorderBeam, NumberTicker
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/
git commit -m "feat: add framer-motion page transitions and micro-interactions"
```

---

### Task 13: TypeScript strict cleanup + build verification

**Files:** Various (fix any TS errors)

**Dependencies:** Task 12

- [ ] **Step 1: Run TypeScript check**

```bash
cd dashboard
npx tsc --noEmit 2>&1
```

- [ ] **Step 2: Fix all TypeScript errors**

Common issues:
- Missing type annotations on event handlers
- Undefined variable references from deleted mock data
- Incorrect prop types from JSX → TSX conversion

- [ ] **Step 3: Verify production build**

```bash
npm run build
# Should complete with no errors
```

- [ ] **Step 4: Verify dev server and backend proxy**

```bash
npm run dev
# Open http://localhost:5173/dashboard/
# Verify: login works, cameras load from backend, alerts stream via SSE
```

- [ ] **Step 5: Verify Python tests still pass**

```bash
cd ..
python -m pytest tests/ --tb=short -q
# Should still be 394 passed
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/
git commit -m "fix: TypeScript strict cleanup, build passes"
```

---

### Task 14: Replace old dashboard and final verification

**Files:**
- Delete: `dashboard-old/` (backup of old dashboard)
- Modify: Root project files if needed

**Dependencies:** Task 13

- [ ] **Step 1: Remove old dashboard backup**

```powershell
Remove-Item -Recurse -Force dashboard-old
```

- [ ] **Step 2: Final end-to-end test**

```bash
# Start backend
python -m fusion_server.main

# Start frontend
cd dashboard && npm run dev

# Test all flows:
# 1. Login at /login
# 2. Dashboard shows camera grid with live feeds
# 3. Alerts appear via SSE
# 4. Click alert → detail panel slides out
# 5. Event history loads from backend
# 6. Map shows camera markers
# 7. Detection overlay works on webcam
# 8. Animations: BorderBeam, NumberTicker, page transitions, hover effects
```

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/ --tb=short -q
# 394 passed
```

- [ ] **Step 4: Push to GitHub**

```bash
git add -A
git commit -m "feat: replace dashboard with BorderEye redesign + Magic UI animations"
git push origin main
```

- [ ] **Step 5: Update AGENTS.md if needed**

Document new dashboard tech stack and architecture.

---

## Summary

| Task | Description | Dependencies |
|------|-------------|--------------|
| 1 | Scaffold project, upgrade deps | None |
| 2 | Delete mocks and dead code | 1 |
| 3 | Unified dark theme + Tailwind v4 | 2 |
| 4 | Port TypeScript types + API + SSE | 1 |
| 5 | Port UI primitives | 3 |
| 6 | Port layout components | 5 |
| 7 | Port camera components | 4, 5 |
| 8 | Port alert components | 4, 5 |
| 9 | Port remaining components | 5 |
| 10 | Wire auth, routes, pages, SSE | 6-9 |
| 11 | Add Magic UI + shadcn/ui | 10 |
| 12 | Add framer-motion animations | 11 |
| 13 | TypeScript cleanup + build verify | 12 |
| 14 | Replace old dashboard + final test | 13 |
