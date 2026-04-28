"""MastekoFM API — FastAPI application.

Sprint B (v2.000+): legacy TGV system + DAG + per-project Datasources removed.
Three-way composition (Project + AssumptionPack + Model + OutputTemplate -> Run)
is the only architecture.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import (
    assumption_packs,
    auth,
    connections,
    health,
    models,
    output_templates,
    projects,
    runs,
    seed,
    settings,
    tree,
    workspaces,
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
app.include_router(workspaces.router)
app.include_router(projects.router)
app.include_router(models.router)
app.include_router(output_templates.router)
app.include_router(assumption_packs.router)
app.include_router(runs.router)
app.include_router(settings.router)
app.include_router(seed.router)
# Sprint A.5 — Tree Navigator endpoints
app.include_router(tree.router)
# Sprint I-2 — workspace connection management (Airtable etc.)
app.include_router(connections.router)
