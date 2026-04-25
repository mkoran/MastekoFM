"""MastekoFM API — FastAPI application."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import (
    assumptions,
    auth,
    dag,
    datasources,
    excel_projects,
    excel_seed,
    excel_templates,
    health,
    output_templates,
    projects,
    runs,
    scenarios,
    seed,
    spreadsheets,
    template_groups,
    templates,
)

app = FastAPI(
    title="MastekoFM API",
    version=os.getenv("VERSION", "0.0.0"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://dev-masteko-fm.web.app",
        "https://masteko-fm.web.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(assumptions.router)
app.include_router(datasources.router)
app.include_router(templates.router)
app.include_router(spreadsheets.router)
app.include_router(dag.router)
app.include_router(template_groups.router)
# Excel Template MVP (tab-prefix architecture) — I_/O_ tabs, scenarios, calculate
app.include_router(excel_templates.router)
app.include_router(excel_projects.router)
app.include_router(scenarios.router)
app.include_router(excel_seed.router)
# Sprint A — three-way composition: OutputTemplates + Runs + Hello World seed
app.include_router(output_templates.router)
app.include_router(runs.router)
app.include_router(seed.router)
