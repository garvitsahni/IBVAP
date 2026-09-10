# AGENTS.md — IBVAP Coding Agent Guardrails

This file governs how any coding agent (human or AI) contributes to this repository. Read this before writing code in any phase.

## 1. Non-Negotiable Architectural Rules

1. **Never let an ML model make a final alert decision.** Detection/classification models produce inputs (bounding boxes, embeddings, scores). The rule engine — plain geometry/threshold logic — is the only thing allowed to set `alert.status = fired`. If you find yourself writing `if model_confidence > X: fire_alert()`, stop and route it through the rule engine instead.
2. **No raw video ever crosses the edge → fusion server boundary, let alone leaves the BOP.** Only structured events, embeddings, and short event-triggered clips are allowed across that boundary. Any code that streams full video off the edge node is a violation of the core sovereignty requirement — reject it in review.
3. **The ledger write is synchronous and blocking; everything else after alert-fire is async.** Do not refactor the ledger write onto a background queue "for performance" — tamper-evidence requires the hash chain to be written before the system considers the alert fully logged.
4. **AI enrichment never blocks alert delivery.** The alert must already be visible on the dashboard before any LLM/VLM call is made. If enrichment is slow, that's fine — it updates the alert record later. It must never be in the critical path.
5. **Data contracts in ARCHITECTURE.md Section 5 are frozen.** Do not change a field name, type, or remove a field without updating that document and flagging it to every phase owner in the same PR.

## 2. Verification Discipline

- **Reproduce before you fix.** Never patch a bug you haven't reproduced locally with real (or realistically simulated) input. A fix for a bug you can't reproduce is a guess, not a fix.
- **Raw terminal output, not agent-summarized output.** When verifying a change (tests passing, pipeline running, model loading), always check the actual raw output — do not trust a coding agent's own summary of "it works" without seeing the output yourself.
- **Git checkpoint before any risky change.** Commit working state before touching re-ID matching thresholds, ledger hash logic, or the rule engine — these are the hardest things to debug after the fact if broken silently.

## 3. No Faking Rule

This project's explicit standard is: **every shipped feature must work on real input, not scripted/staged demo data.**
- Do not hardcode a "demo path" that only works for one rehearsed input and silently fails otherwise, without a visible degraded/failure state.
- Do not simulate a feature's output without also implementing the underlying logic (e.g., no pre-written "AI explanation" strings — the enrichment service must actually call the model).
- If a feature genuinely cannot be validated yet (e.g., power-loss resilience without real hardware), it must be clearly marked `[SIMULATED / UNIT-TESTED ONLY]` in its module docstring and in the phase tracker — never presented as field-validated.

## 4. Scope Discipline

- Features are assigned to phases (see PHASES.md). Do not start Phase 4 work before Phase 1–3 contracts are stable unless explicitly agreed — this is how integration debt happens on a 5-person team.
- If you think a feature should be cut or deferred, raise it — don't silently stub it and move on. This project's owner has explicitly chosen to keep every feature real rather than cut to roadmap-only; deviating from that requires an explicit decision, not a unilateral shortcut.

## 5. Tech Stack Constraints

- Backend: FastAPI (Python) only — no introducing a second backend framework for a sub-feature.
- Detection models: YOLOv8n baseline for CPU/laptop-stage development. Do not swap to a heavier model without confirming it still runs acceptably on the team's current hardware (laptop-class, per PRD Section 3).
- Storage: PostgreSQL for structured data, local filesystem/MinIO for clips — no external managed DB or cloud storage service, ever, per the sovereignty requirement.
- No cloud API calls for core functionality (detection, tracking, re-ID, ledger, alerting). AI enrichment must use a locally-hosted model, not an external API, once past the earliest prototyping stage.

## 6. Review Checklist (apply to every PR)

- [ ] Does this change respect the deterministic-vs-AI decision boundary (Rule 1)?
- [ ] Does any data cross the BOP boundary that shouldn't (Rule 2)?
- [ ] Is the ledger write still synchronous (Rule 3)?
- [ ] Does this block alert delivery on anything AI-related (Rule 4)?
- [ ] Does this touch a frozen data contract without updating ARCHITECTURE.md (Rule 5)?
- [ ] Is anything faked, stubbed, or hardcoded in a way that would misrepresent this as working when it isn't (Section 3)?
- [ ] Is the raw output of tests/pipeline runs actually verified, not just agent-reported?
