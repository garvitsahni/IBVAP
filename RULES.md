# IBVAP — Team & Development Rules

Distinct from AGENTS.md (which governs coding-agent behavior on this codebase) — this covers how the human team works together.

## 1. Working Agreement

- **No fixed deadline does not mean no accountability.** Each phase (see PHASES.md) has an exit criteria — a live demo on real/simulated input. A phase isn't "done" until that demo happens in front of the rest of the team.
- **Data contracts (ARCHITECTURE.md Section 5) are frozen at Phase 0.** Any change requires a message to the whole team before merging, not after.
- **Whoever owns a phase owns its demo.** If you built it, you show it working — not a teammate describing it on your behalf.

## 2. Git Workflow

- Feature branches per phase/feature, not one giant shared branch.
- Commit checkpoints before touching: re-ID matching thresholds, ledger hash logic, rule engine geometry. These are the hardest things to debug if broken silently — a clean rollback point matters more here than elsewhere.
- PR review required before merging into the integration branch — at minimum, one other team member confirms the AGENTS.md review checklist.

## 3. Testing Standard

- Every feature must be demoed on real or realistically simulated input before being marked complete — no feature is "done" based on unit tests passing alone if it's a perception/detection feature (visual confirmation matters here).
- Reproduce every bug locally before attempting a fix. A fix for an unreproduced bug is a guess.
- When verifying a pipeline run or test suite, check the actual raw output yourself — do not accept a coding agent's summary as verification.

## 4. Definition of "Working" (the standard for this project)

A feature is only "working" if:
1. It runs on real or realistically simulated input, not scripted/staged demo-only paths.
2. It behaves correctly outside the one rehearsed demo scenario (test at least one edge case: different lighting, a second camera angle, an unexpected object).
3. Any known limitation is documented explicitly (e.g., "validated in simulation only, not on real edge hardware") rather than hidden.

This is the standard the whole project has been scoped around — features that don't meet it get marked `[SIMULATED / UNIT-TESTED ONLY]`, not presented as complete.

## 5. Communication

- Blockers get raised the same day, not saved for a sync — with a 5-person team building in parallel against shared data contracts, a silent blocker on one phase stalls whoever depends on it.
- Any decision to cut, defer, or simplify a feature from the finalized set in the PRD is a team decision, not a unilateral one — the project's owner explicitly chose to keep every feature real rather than roadmap-only, so scope changes need to be surfaced, not quietly made.

## 6. Documentation Upkeep

- PRD.md, ARCHITECTURE.md, PHASES.md, and DESIGN_SYSTEM.md are living documents. If a phase's implementation diverges from what's written (e.g., a data contract field changes, a phase's scope shifts), update the document in the same PR — not "later."
