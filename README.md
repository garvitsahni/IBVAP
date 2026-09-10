# IBVAP — Documentation Index

This is the full documentation set for building IBVAP as a fully functional MVP — every feature real, no faked demos.

Read in this order:

1. **IBVAP_PRD.md** — Product requirements: problem statement, vision, finalized feature set (25 features), success criteria, risks.
2. **ARCHITECTURE.md** — Technical architecture: system topology, component breakdown, alert lifecycle, frozen data contracts, deployment stages.
3. **PHASES.md** — Phased execution plan mapped to a 5-person team, with exit criteria per phase.
4. **AGENTS.md** — Guardrails for any coding agent (human or AI) contributing code — the non-negotiable architectural rules and the "no faking" standard.
5. **RULES.md** — Team working agreement: git workflow, testing standard, definition of "working," communication norms.
6. **DESIGN_SYSTEM.md** — UI/UX design system for the command dashboard and patrol companion app.

## Core Thesis (keep this in view at every phase)

A fully sovereign, edge-native video analytics platform that turns existing BOP CCTV into a self-auditing surveillance mesh — every object tracked across every camera with a tamper-evident local footprint, alerts fired at machine speed before AI is ever involved, and zero data leaving the post.

## Non-negotiables across all documents

- Deterministic engines decide alerts; AI only explains and predicts, after the fact, non-blocking.
- Nothing leaves the BOP.
- Every shipped feature works on real input — nothing faked, nothing staged-only without being clearly labeled as such.
