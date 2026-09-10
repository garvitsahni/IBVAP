# IBVAP — Design System

Applies to the Command Dashboard and the Patrol Companion App. Goal: an interface a guard or operator can trust and act on under stress, not a generic admin panel.

## 1. Design Principles

1. **Alert visibility beats aesthetics.** Nothing in the UI should ever slow down recognizing and acting on a live alert. High-priority alerts must be impossible to miss.
2. **Show the evidence, not just the verdict.** Every alert links to its footprint chain, its overlay clip, and its ledger status — an operator should never have to take an alert on faith.
3. **Distinguish deterministic facts from AI commentary.** The rule-fired alert (fact) and the AI enrichment (interpretation) must be visually distinct — different styling, clearly labeled — so operators never confuse a system-verified event with an AI guess.
4. **Degraded states are loud, not subtle.** Camera down, reduced-accuracy mode, low-confidence-due-to-weather — these get a persistent, unambiguous visual treatment, never a small icon easy to miss.
5. **Works on a LAN, works under pressure.** No dependency on external fonts/CDNs/assets for the patrol app; keep it lightweight enough to run responsively on modest hardware over local Wi-Fi.

## 2. Color System

| Token | Use | Example |
|---|---|---|
| `--alert-critical` | Fired, high-threat-score alerts | Deep red |
| `--alert-standard` | Fired, standard alerts | Amber |
| `--ai-enrichment` | AI-generated explanation/trajectory content | Muted blue/purple — visually distinct from alert colors |
| `--system-ok` | Camera healthy, ledger verified | Green |
| `--system-degraded` | Camera down, reduced-accuracy mode, low-confidence flag | Bold orange, persistent banner treatment |
| `--system-compromised` | Camera tamper/blinding detected, ledger break detected | Red with a distinct icon from `--alert-critical` so operators don't confuse "an intrusion happened" with "the system itself is compromised" |
| `--neutral-*` | Backgrounds, text, chrome | Dark-mode-first palette (control rooms are often dim) |

## 3. Typography

- Dashboard: a clean, highly legible sans-serif (e.g., Inter or system-ui stack) — prioritize legibility at a glance over personality.
- Numeric/timestamp data (ledger hashes, coordinates, timestamps) in a monospace font to reinforce that this is precise, machine-verified data, not prose.

## 4. Core Screens

### 4.1 Live Alert Queue
- Priority-ranked list (by threat score), critical alerts pinned to top with persistent visual weight.
- Each alert card: camera ID, timestamp, reason (deterministic, factual language — "Human detected crossing North Fence Line"), threat score, status badge (`fired` vs `enriched`).
- Clicking an alert opens the full record: overlay clip, footprint chain, AI enrichment (clearly labeled and visually separated), ledger verification status.

### 4.2 Footprint Chain Viewer
- A simple timeline/graph view: camera nodes in the order the object was seen, with timestamps on each hop.
- Should answer "where did this come from and where did it go" in a single glance — this is your core differentiator, don't bury it in a data table.

### 4.3 Camera Grid / Coverage Map
- Live feed thumbnails with per-camera health indicator (`--system-ok` / `--system-degraded` / `--system-compromised`).
- Overlaid blind-spot map: configured ROIs shown as covered regions, computed gaps shown in a clearly different, "needs attention" color.

### 4.4 Ledger Status Panel
- Simple, persistent indicator: chain verified / chain broken. If broken, show exactly which entry and when the break was detected.

### 4.5 Patrol Companion App (LAN-only)
- Stripped down to: incoming alert push (loud, hard to miss), footprint chain summary, trajectory overlay on a simple map. No configuration screens, no ledger internals — this app is for immediate field action, not administration.

## 5. Interaction Rules

- Critical alerts require explicit acknowledgment (a tap/click), not auto-dismiss — this creates an audit trail of "this was seen by a human at time X," which pairs naturally with the ledger's evidentiary purpose.
- Never let an AI-enriched explanation replace the original deterministic reason string in the UI — always show both, enrichment appended below the fact.
