# MastekoFM — Session Handoff

> Last updated: 2026-04-15
> Version: see VERSION file

## Project overview
MastekoFM is a financial modelling SaaS platform. See ARCHITECTURE.md for full design.

## Current state
- Sprint 0: Infrastructure skeleton
- GCP project: masteko-fm
- GitHub repo: github.com/mkoran/MastekoFM

## Key file locations
- Design rules: CLAUDE.md
- Architecture: ARCHITECTURE.md
- Backlog: BACKLOG.md
- Lessons from MastekoDWH: LESSONS_LEARNED.md
- Backend entry point: backend/app/main.py
- Frontend entry point: frontend/src/App.tsx
- Deploy scripts: deploy-dev.sh, deploy-prod.sh

## What was done
- Sprint 0 kickoff: full repository scaffold, GCP infra, CI/CD pipeline

## What's next
- Sprint 1: Core data model + project CRUD + auth flow

## Blockers
- None

## Decisions made
- Excel engine: LibreOffice headless (always), not openpyxl formula evaluator
- Multi-user: checkout model (project-level lock)
- Real-time: Firestore onSnapshot listeners
- Airtable: ingest-only in v1
