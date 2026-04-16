# MastekoFM — Session Handoff

> Last updated: 2026-04-16
> Version: 1.027 (see VERSION file)

## Project overview
MastekoFM is a financial modelling SaaS platform. Users create projects, connect data sources, manage assumptions (key-values + tables), and generate calculated Excel output files via LibreOffice headless.

## Current state — v1.027

### Completed Sprints
- **Sprint 0**: GCP project (masteko-fm), Cloud Run, Firebase Hosting, CI/CD
- **Sprint 1**: Auth (Firebase + DEV bypass), Project CRUD, Assumptions CRUD, Checkout system
- **Sprint 2**: Data source connectors (CSV, Excel, Airtable), field discovery, sync
- **Table Assumptions**: Row-based editable grids, Assumption Templates
- **UI Overhaul**: Left sidebar nav, project table, full template CRUD
- **Campus Adele**: Real 15-sheet construction-to-perm model loaded (64 units, 170 budget items)
- **Sprint 3-5**: Excel engine (LibreOffice double-conversion xlsx→ods→xlsx), calculation pipeline, output download
- **Template Groups Sprint**: Template Groups, Template Group Values (scenarios), app settings, scenario editor

### Live Environment
- **DEV API**: masteko-fm-api-dev-560873149926.northamerica-northeast1.run.app
- **DEV Frontend**: dev-masteko-fm.web.app
- **GCP Project**: masteko-fm (project number: 560873149926)
- **GCS Output Bucket**: masteko-fm-outputs (public read)
- **Tests**: 67 passing
- **CI**: GitHub Actions — green on main

### Key Concepts
| Concept | Description |
|---------|-------------|
| **Assumption Template** | Named set of key-value + table definitions (e.g. Revenue, Budget) |
| **Template Group** | Collection of templates that define a complete model structure |
| **Template Group Value (TGV)** | Named scenario = all values for a template group (e.g. "Base Case", "Optimistic") |
| **Project** | Has a template group + multiple TGVs. Excel model uploaded. Calculate injects TGV values. |

### Campus Adele Project
- Project ID: W7iv0qXuHAykO7yDP2Wd
- Template Group: "Construction-to-Permanent" (ID: ppOOp71m0TNgYJtrevM0)
- Scenarios: Base Case (populated with 36 values), Optimistic (cloned)
- Excel model: 15-sheet construction-to-perm financing model
- Input mappings: 36 assumption keys → Excel cell references
- Verified: output matches original Excel (Revenue, NOI, Financing all correct)

## Key file locations
- CLAUDE.md — Development rules
- ARCHITECTURE.md — Technical architecture
- BACKLOG.md — Product backlog (needs Template Groups update)
- backend/app/main.py — FastAPI app (10 routers)
- backend/app/services/excel_engine.py — LibreOffice calculation
- backend/app/services/dag_executor.py — Calculation pipeline (inject → calc → upload)
- backend/app/services/drive_service.py — Google Drive (uses user's OAuth token)
- backend/app/routers/template_groups.py — Template Groups + TGV + Settings API
- frontend/src/App.tsx — React Router (12 routes)
- frontend/src/components/Layout.tsx — Left sidebar nav
- frontend/src/pages/ScenarioEditor.tsx — TGV value editor

## What's next
- **Google Drive integration**: Sign in with Google → Test Drive → Calculate → file appears in Drive
  - OAuth client created: 560873149926-t2fac73e3hu23seb4care19qfpv72a5c.apps.googleusercontent.com
  - Drive scope requested during Google Sign-In
  - User's OAuth token passed to backend for Drive uploads
  - Enable Google Auth in Firebase Console to complete
- **Template Group Value comparison** (future): diff two scenarios side-by-side
- **Airtable → Unit Rent Roll** (future user story): connect Airtable to populate rent roll table

## Known issues
- Google Sign-In needs Firebase Auth Google provider fully configured (OAuth consent screen may need verification for external users)
- DEV login works for everything except Drive uploads (Drive requires real Google OAuth)
- LibreOffice double-conversion (xlsx→ods→xlsx) adds ~10s to calculation time

## Decisions made
- Excel engine: LibreOffice headless (double-conversion for formula recalculation)
- Drive uploads: user's Google OAuth token (not service account — personal Gmail limitation)
- GCS fallback: masteko-fm-outputs bucket for when Drive isn't available
- Template Group Values replace per-project assumptions for scenario management
- Output folder structure: ProjectCode/TGVCode/YYYYMMDDHHMM_ProjectCode_TGVCode/
